import asyncio
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings, APP_VERSION
from app import companion
from app import notifier
from app import triggers as trigger_engine

def _select_store():
    """Pick the data backend based on DATA_BACKEND."""
    backend = settings.DATA_BACKEND
    if backend == "sheets":
        from app import sheets as chosen
    elif backend == "sqlite":
        from app import sqlite_store as chosen
    elif backend == "memory":
        from app import store as chosen
    else:
        raise ValueError(
            f"Invalid DATA_BACKEND={backend!r}; expected one of: sheets, sqlite, memory"
        )

    # Deprecation warning when the legacy flag was the sole signal
    if os.getenv("DATA_BACKEND") is None and settings.USE_GOOGLE_SHEETS:
        print(
            "[config] USE_GOOGLE_SHEETS is deprecated — set DATA_BACKEND=sheets instead"
        )
    print(f"[config] DATA_BACKEND={backend}")
    return chosen


store = _select_store()
from app.models import ACT_CATEGORIES, Act
from app.slip import calculate_slip, format_variance
from app.websocket import manager

# Art-Net listener (initialized on startup if enabled)
artnet_listener: Optional["ArtNetListener"] = None

# Background polling task
_polling_task: Optional[asyncio.Task] = None
POLL_INTERVAL_SECONDS = 30


async def poll_schedule():
    """Periodically fetch schedule from Google Sheets and broadcast updates."""
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        try:
            store.write_active_screentimes()
            acts = store.get_schedule()

            if trigger_engine.is_enabled():
                newly_triggered = trigger_engine.check_and_fire(acts)
                completed_cleared = trigger_engine.clear_completed(acts)
                if newly_triggered or completed_cleared:
                    await manager.broadcast_recording_state(trigger_engine.get_active_reminders(), trigger_engine.is_enabled())

            notifier.check_and_notify(acts)
            await broadcast_schedule_update()
        except Exception as e:
            print(f"Error polling schedule: {e}")


async def on_brightness_change(value: int) -> None:
    """Callback for Art-Net brightness value changes."""
    await manager.broadcast_brightness(value)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global artnet_listener, _polling_task

    if settings.DATA_BACKEND == "sqlite":
        from app.db import init_db
        init_db()

    if settings.ARTNET_ENABLED:
        from app.artnet import ArtNetListener
        artnet_listener = ArtNetListener(
            port=settings.ARTNET_PORT,
            universe=settings.ARTNET_UNIVERSE,
            bit_depth=settings.ARTNET_BIT_DEPTH,
            channel=settings.ARTNET_CHANNEL,
            channel_high=settings.ARTNET_CHANNEL_HIGH,
            channel_low=settings.ARTNET_CHANNEL_LOW,
            max_nits=settings.ARTNET_MAX_NITS,
            callback=on_brightness_change,
        )
        await artnet_listener.start()

    # Start background polling for schedule updates
    _polling_task = asyncio.create_task(poll_schedule())

    if settings.AUTO_RELOAD_ON_STARTUP:
        async def _startup_reload():
            await asyncio.sleep(settings.STARTUP_RELOAD_DELAY)
            await manager.broadcast_reload()
            print(f"[startup] broadcast hard-reload to all clients after {settings.STARTUP_RELOAD_DELAY}s delay")
        asyncio.create_task(_startup_reload())

    yield

    # Shutdown
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass

    if artnet_listener:
        artnet_listener.stop()


app = FastAPI(title="Festival Schedule Board", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

_http_basic = HTTPBasic(auto_error=False)


def _require_edit_auth(credentials: Optional[HTTPBasicCredentials] = Depends(_http_basic)):
    """Enforce HTTP Basic Auth on the edit page when EDIT_PASSWORD is set."""
    if not settings.EDIT_PASSWORD:
        return
    ok = credentials is not None and secrets.compare_digest(
        credentials.password.encode(), settings.EDIT_PASSWORD.encode()
    )
    if not ok:
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Schedule Editor"'},
        )



def get_template_context(request: Request = None) -> dict:
    """Build the common template context."""
    acts = store.get_schedule()
    slip = calculate_slip(acts)
    return {
        "request": request,
        "stage_name": store.get_stage_name(),
        "acts": acts,
        "slip": slip,
        "format_variance": format_variance,
        "sheet_tab": store.get_current_show() if settings.DATA_BACKEND == "sheets" else None,
        "data_backend": settings.DATA_BACKEND,
        "timezone": settings.TIMEZONE,
        "has_next_show": store.has_next_show(),
        "current_show": store.get_current_show(),
        "next_show": store.get_next_show(),
        "app_version": APP_VERSION,
        "kipro_configured": bool(settings.KIPRO_IP),
        "weather_configured": bool(settings.WEATHER_URL),
        "public_url": settings.PUBLIC_URL,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the view-only schedule page."""
    context = get_template_context(request)
    context["view_only"] = True
    context["show_time_override"] = False
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/edit", response_class=HTMLResponse)
async def edit(request: Request, _=Depends(_require_edit_auth)):
    """Render the operator schedule page with controls."""
    context = get_template_context(request)
    context["view_only"] = False
    context["show_time_override"] = False
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/stage", response_class=HTMLResponse)
async def stage(request: Request):
    """Big-display stage board: stage name, clock, and up-next artist."""
    context = get_template_context(request)
    context["view_only"] = True
    context["show_time_override"] = False
    return templates.TemplateResponse(request, "stage.html", context)


@app.get("/preview", response_class=HTMLResponse)
async def preview(request: Request):
    """Read-only schedule view with time-of-day override for previewing layout."""
    context = get_template_context(request)
    context["view_only"] = False
    context["show_time_override"] = True
    return templates.TemplateResponse(request, "index.html", context)


@app.post("/acts/{act_name}/start")
async def record_start(act_name: str):
    """Record the actual start time for an act."""
    act_name = unquote(act_name)
    current_time = datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()

    # Auto-complete any currently in-progress act
    for act in store.get_schedule():
        if act.is_in_progress():
            store.update_actual_end(act.act_name, current_time)
            break

    act = store.update_actual_start(act_name, current_time)

    if act:
        notifier.notify_act_started(act_name, current_time.strftime("%H:%M"))
        companion.trigger_set_mv_rec()
        await broadcast_schedule_update()

    return {"status": "ok"}


@app.post("/acts/{act_name}/end")
async def record_end(act_name: str):
    """Record the actual end time for an act."""
    act_name = unquote(act_name)
    current_time = datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()
    act = store.update_actual_end(act_name, current_time)

    if act:
        notifier.notify_act_ended(act_name, current_time.strftime("%H:%M"))
        companion.trigger_changeover_rec()
        await broadcast_schedule_update()

    return {"status": "ok"}


@app.post("/acts/{act_name}/screentime/start")
async def screentime_start(act_name: str):
    """Start on-deck screentime for an act."""
    act_name = unquote(act_name)
    act = store.start_screentime(act_name)

    if act:
        await broadcast_schedule_update()

    return {"status": "ok"}


@app.post("/acts/{act_name}/screentime/stop")
async def screentime_stop(act_name: str):
    """Stop on-deck screentime for an act and persist total."""
    act_name = unquote(act_name)
    act = store.stop_screentime(act_name)

    if act:
        await broadcast_schedule_update()

    return {"status": "ok"}


@app.post("/acts/{act_name}/clear")
async def clear_times(act_name: str):
    """Clear actual times for an act."""
    act_name = unquote(act_name)
    act = store.clear_actual_times(act_name)

    if act:
        await broadcast_schedule_update()

    return {"status": "ok"}


@app.get("/api/next-act")
async def get_next_act():
    """Get the next act that hasn't started yet, with seconds until projected start."""
    acts = store.get_schedule()
    slip = calculate_slip(acts)
    now = datetime.now(tz=ZoneInfo(settings.TIMEZONE))

    for act in acts:
        if act.actual_start is None:
            projected_start = datetime.combine(now.date(), act.scheduled_start, tzinfo=ZoneInfo(settings.TIMEZONE)) + timedelta(seconds=slip)
            seconds_until = int((projected_start - now).total_seconds())
            return {
                "act_name": act.act_name,
                "scheduled_start": act.scheduled_start.strftime("%H:%M"),
                "projected_start": projected_start.strftime("%H:%M"),
                "slip_seconds": slip,
                "seconds_until": seconds_until,
            }

    return {"act_name": None, "seconds_until": None}


@app.get("/api/time")
async def get_server_time():
    """Return the current server time as UTC epoch ms, for client clock sync."""
    now = datetime.now(tz=ZoneInfo(settings.TIMEZONE))
    return {"epoch_ms": int(now.timestamp() * 1000)}


@app.get("/api/brightness")
async def get_brightness():
    """Get the current brightness value from Art-Net."""
    if artnet_listener:
        return {"value": artnet_listener.current_value}
    return {"value": manager.current_brightness}


def build_schedule_html(acts: list[Act], view_only: bool) -> str:
    """Build HTML for all act rows."""
    html_parts = []
    for act in acts:
        act_html = templates.get_template("components/act_row.html").render(
            act=act,
            format_variance=format_variance,
            view_only=view_only,
        )
        html_parts.append(act_html)
    return f'<div id="schedule-list" hx-swap-oob="innerHTML">{"".join(html_parts)}</div>'


async def broadcast_schedule_update():
    """Broadcast the updated schedule to all connected clients."""
    acts = store.get_schedule()

    # Build HTML for viewers (no buttons) and editors (with buttons)
    viewer_html = build_schedule_html(acts, view_only=True)
    editor_html = build_schedule_html(acts, view_only=False)

    await manager.broadcast_schedule(viewer_html, editor_html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, mode: str = "view"):
    """WebSocket endpoint for real-time sync."""
    is_editor = mode == "edit"
    await manager.connect(websocket, is_editor=is_editor)
    try:
        while True:
            # Keep connection alive, receive any messages (we don't process them)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)



@app.post("/api/show/advance")
async def advance_show():
    """Advance to the next show tab. Broadcasts a reload to all connected clients."""
    if settings.DATA_BACKEND == "memory":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Multi-show switching requires a persistent backend")
    if not store.has_next_show():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Already on the last show")
    store.advance_show()
    await broadcast_schedule_update()
    await manager.broadcast_reload()
    return {"status": "ok", "tab": store.get_current_show()}


@app.post("/api/kipro/record")
async def kipro_record():
    """Manually start recording on the Ki Pro."""
    from app import recorder
    recorder.start_recording("manual")
    return {"status": "ok"}


@app.post("/api/kipro/stop")
async def kipro_stop():
    """Manually stop recording on the Ki Pro."""
    from app import recorder
    recorder.stop_recording("manual")
    return {"status": "ok"}


@app.get("/api/weather")
async def get_weather():
    """Fetch current weather from the configured WeatherLink endpoint."""
    import json
    import urllib.request

    def _fetch():
        try:
            with urllib.request.urlopen(settings.WEATHER_URL, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            return {
                "temperature": data.get("temperature"),
                "wind": data.get("wind"),
                "gust": data.get("gust"),
                "windDirection": data.get("windDirection"),
                "humidity": data.get("humidity"),
                "windUnits": data.get("windUnits", "mph"),
                "tempUnits": "°F",
                "lastReceived": data.get("lastReceived"),
            }
        except Exception as e:
            return {"error": str(e)}

    return await asyncio.to_thread(_fetch)


@app.get("/api/kipro/status")
async def kipro_status():
    """Query Ki Pro transport state — returns whether the deck is currently rolling."""
    import asyncio
    from app import recorder
    return await asyncio.to_thread(recorder.get_transport_state)


@app.post("/api/recording/toggle")
async def recording_toggle():
    """Toggle recording triggers on/off at runtime."""
    trigger_engine.set_enabled(not trigger_engine.is_enabled())
    await manager.broadcast_recording_state(trigger_engine.get_active_reminders(), trigger_engine.is_enabled())
    return {"enabled": trigger_engine.is_enabled()}


@app.post("/acts/{act_name}/recording/stop")
async def recording_stop(act_name: str):
    """Operator-initiated stop: calls stop_recording() and clears the reminder."""
    act_name = unquote(act_name)
    trigger_engine.stop_and_dismiss(act_name)
    await manager.broadcast_recording_state(trigger_engine.get_active_reminders(), trigger_engine.is_enabled())
    return {"status": "ok"}


@app.post("/acts/{act_name}/recording/dismiss")
async def recording_dismiss(act_name: str):
    """Dismiss the recording reminder without calling stop_recording()."""
    act_name = unquote(act_name)
    trigger_engine.dismiss(act_name)
    await manager.broadcast_recording_state(trigger_engine.get_active_reminders(), trigger_engine.is_enabled())
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Admin UI — SQLite-only schedule editor (gated by EDIT_PASSWORD)
# ---------------------------------------------------------------------------

def _parse_time_field(value: str):
    if not value:
        return None
    from datetime import datetime as _dt
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return _dt.strptime(value, fmt).time()
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail=f"Invalid time: {value!r}")


def _require_sqlite():
    if settings.DATA_BACKEND != "sqlite":
        raise HTTPException(status_code=400, detail="Admin UI requires DATA_BACKEND=sqlite")


@app.get("/admin", response_class=HTMLResponse)
async def admin_shows(request: Request, _=Depends(_require_edit_auth)):
    context = {
        "request": request,
        "app_version": APP_VERSION,
        "data_backend": settings.DATA_BACKEND,
        "shows": store.list_shows() if settings.DATA_BACKEND == "sqlite" else [],
    }
    return templates.TemplateResponse(request, "admin/shows.html", context)


@app.post("/admin/shows")
async def admin_create_show(request: Request, _=Depends(_require_edit_auth)):
    _require_sqlite()
    form = await request.form()
    name = (form.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    make_current = bool(form.get("make_current"))
    try:
        store.create_show(name, make_current=make_current)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/shows/{show_id}/delete")
async def admin_delete_show(show_id: int, _=Depends(_require_edit_auth)):
    _require_sqlite()
    store.delete_show(show_id)
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/shows/{show_id}/current")
async def admin_set_current_show(show_id: int, _=Depends(_require_edit_auth)):
    _require_sqlite()
    store.set_current_show(show_id)
    await broadcast_schedule_update()
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/shows/{show_id}/rename")
async def admin_rename_show(show_id: int, request: Request, _=Depends(_require_edit_auth)):
    _require_sqlite()
    form = await request.form()
    name = (form.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    store.rename_show(show_id, name)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/admin/shows/{show_id}", status_code=303)


@app.get("/admin/shows/{show_id}", response_class=HTMLResponse)
async def admin_show_detail(show_id: int, request: Request, _=Depends(_require_edit_auth)):
    _require_sqlite()
    show = store.get_show_detail(show_id)
    if show is None:
        raise HTTPException(status_code=404, detail="Show not found")
    context = {
        "request": request,
        "app_version": APP_VERSION,
        "data_backend": settings.DATA_BACKEND,
        "show": show,
        "act_categories": ACT_CATEGORIES,
    }
    return templates.TemplateResponse(request, "admin/show_detail.html", context)


@app.post("/admin/shows/{show_id}/acts")
async def admin_add_act(show_id: int, request: Request, _=Depends(_require_edit_auth)):
    _require_sqlite()
    show = store.get_show_detail(show_id)
    if show is None:
        raise HTTPException(status_code=404, detail="Show not found")
    form = await request.form()
    act_name = (form.get("act_name") or "").strip()
    if not act_name:
        raise HTTPException(status_code=400, detail="act_name required")
    store.add_act(
        show["name"],
        act_name=act_name,
        scheduled_start=_parse_time_field(form.get("scheduled_start", "")),
        scheduled_end=_parse_time_field(form.get("scheduled_end", "")),
        category=form.get("category") or None,
    )
    await broadcast_schedule_update()
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/admin/shows/{show_id}", status_code=303)


@app.post("/admin/acts/{act_id}/update")
async def admin_update_act(act_id: int, request: Request, _=Depends(_require_edit_auth)):
    _require_sqlite()
    form = await request.form()
    end_raw = form.get("scheduled_end", "")
    store.update_act(
        act_id,
        act_name=(form.get("act_name") or "").strip() or None,
        scheduled_start=_parse_time_field(form.get("scheduled_start", "")),
        scheduled_end=_parse_time_field(end_raw) if end_raw else None,
        clear_end=(end_raw == ""),
        category=form.get("category") or None,
    )
    await broadcast_schedule_update()
    from fastapi.responses import RedirectResponse
    referer = request.headers.get("referer", "/admin")
    return RedirectResponse(referer, status_code=303)


@app.post("/admin/acts/{act_id}/delete")
async def admin_delete_act(act_id: int, request: Request, _=Depends(_require_edit_auth)):
    _require_sqlite()
    store.delete_act(act_id)
    await broadcast_schedule_update()
    from fastapi.responses import RedirectResponse
    referer = request.headers.get("referer", "/admin")
    return RedirectResponse(referer, status_code=303)


@app.post("/admin/acts/{act_id}/move")
async def admin_move_act(act_id: int, request: Request, _=Depends(_require_edit_auth)):
    _require_sqlite()
    form = await request.form()
    direction = form.get("direction", "up")
    store.move_act(act_id, direction)
    await broadcast_schedule_update()
    from fastapi.responses import RedirectResponse
    referer = request.headers.get("referer", "/admin")
    return RedirectResponse(referer, status_code=303)


@app.post("/admin/import/json")
async def admin_import_json(request: Request, _=Depends(_require_edit_auth)):
    _require_sqlite()
    form = await request.form()
    upload = form.get("file")
    if not hasattr(upload, "read"):
        raise HTTPException(status_code=400, detail="file upload required")
    import json
    try:
        payload = json.loads((await upload.read()).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    try:
        show_id = store.import_show_from_json(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await broadcast_schedule_update()
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/admin/shows/{show_id}", status_code=303)


@app.post("/api/reset")
async def reset_data():
    """Reset all actual times to None (testing only, disabled when DATA_BACKEND=sheets)."""
    if settings.DATA_BACKEND == "sheets":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Reset not allowed in production mode")
    acts = store.get_schedule()
    for act in acts:
        store.clear_actual_times(act.act_name)
    await broadcast_schedule_update()
    return {"status": "reset", "acts_cleared": len(acts)}


@app.post("/api/reload")
async def reload_clients():
    """Force all connected clients to hard-reload the page."""
    await manager.broadcast_reload()
    return {"status": "reload sent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

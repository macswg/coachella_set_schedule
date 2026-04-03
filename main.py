import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app import triggers as trigger_engine

if settings.USE_GOOGLE_SHEETS:
    from app import sheets as store
else:
    from app import store
from app.models import Act
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

    if settings.ARTNET_ENABLED:
        from app.artnet import ArtNetListener
        artnet_listener = ArtNetListener(
            port=settings.ARTNET_PORT,
            universe=settings.ARTNET_UNIVERSE,
            channel_high=settings.ARTNET_CHANNEL_HIGH,
            channel_low=settings.ARTNET_CHANNEL_LOW,
            callback=on_brightness_change,
        )
        await artnet_listener.start()

    # Start background polling for schedule updates
    _polling_task = asyncio.create_task(poll_schedule())

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
        "sheet_tab": store.get_current_show() if settings.USE_GOOGLE_SHEETS else None,
        "use_google_sheets": settings.USE_GOOGLE_SHEETS,
        "has_next_show": store.has_next_show(),
        "current_show": store.get_current_show(),
        "next_show": store.get_next_show(),
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the view-only schedule page."""
    context = get_template_context(request)
    context["view_only"] = True
    context["show_time_override"] = False
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/edit", response_class=HTMLResponse)
async def edit(request: Request):
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
        await broadcast_schedule_update()

    return {"status": "ok"}


@app.post("/acts/{act_name}/end")
async def record_end(act_name: str):
    """Record the actual end time for an act."""
    act_name = unquote(act_name)
    current_time = datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()
    act = store.update_actual_end(act_name, current_time)

    if act:
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
    if not settings.USE_GOOGLE_SHEETS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Multi-show switching requires Google Sheets")
    if not store.has_next_show():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Already on the last show")
    store.advance_show()
    await broadcast_schedule_update()
    await manager.broadcast_reload()
    return {"status": "ok", "tab": store.get_current_show()}


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


@app.post("/api/reset")
async def reset_data():
    """Reset all actual times to None (testing only, disabled when USE_GOOGLE_SHEETS=true)."""
    if settings.USE_GOOGLE_SHEETS:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Reset not allowed in production mode")
    acts = store.get_schedule()
    for act in acts:
        store.clear_actual_times(act.act_name)
    await broadcast_schedule_update()
    return {"status": "reset", "acts_cleared": len(acts)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

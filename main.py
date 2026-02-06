import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from urllib.parse import unquote

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings

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
        "sheet_tab": settings.GOOGLE_SHEET_TAB if settings.USE_GOOGLE_SHEETS else None,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the view-only schedule page."""
    context = get_template_context(request)
    context["view_only"] = True
    return templates.TemplateResponse("index.html", context)


@app.get("/edit", response_class=HTMLResponse)
async def edit(request: Request):
    """Render the operator schedule page with controls."""
    context = get_template_context(request)
    context["view_only"] = False
    return templates.TemplateResponse("index.html", context)


@app.post("/acts/{act_name}/start")
async def record_start(act_name: str):
    """Record the actual start time for an act."""
    act_name = unquote(act_name)
    current_time = datetime.now().time()
    act = store.update_actual_start(act_name, current_time)

    if act:
        await broadcast_schedule_update()

    return {"status": "ok"}


@app.post("/acts/{act_name}/end")
async def record_end(act_name: str):
    """Record the actual end time for an act."""
    act_name = unquote(act_name)
    current_time = datetime.now().time()
    act = store.update_actual_end(act_name, current_time)

    if act:
        await broadcast_schedule_update()

    return {"status": "ok"}


@app.post("/acts/{act_name}/clear")
async def clear_times(act_name: str):
    """Clear actual times for an act."""
    act_name = unquote(act_name)
    act = store.clear_actual_times(act.act_name)

    if act:
        await broadcast_schedule_update()

    return {"status": "ok"}


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



# Reset endpoint for testing

@app.post("/api/reset")
async def reset_data():
    """Reset all actual times to None (testing only)"""
    acts = store.get_schedule()
    for act in acts:
        store.clear_actual_times(act.act_name)
    await broadcast_schedule_update()
    return {"status": "reset", "acts_cleared": len(acts)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

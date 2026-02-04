from datetime import datetime
from urllib.parse import unquote

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import store
from app.slip import calculate_slip, format_variance
from app.websocket import manager

app = FastAPI(title="Festival Schedule Board")

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
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main schedule page."""
    context = get_template_context(request)
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
    act = store.clear_actual_times(act_name)

    if act:
        await broadcast_schedule_update()

    return {"status": "ok"}


async def broadcast_schedule_update():
    """Broadcast the updated schedule to all connected clients."""
    acts = store.get_schedule()
    slip = calculate_slip(acts)

    # Build HTML for all act rows
    html_parts = []
    for act in acts:
        act_html = templates.get_template("components/act_row.html").render(
            act=act,
            format_variance=format_variance,
        )
        html_parts.append(act_html)

    # Wrap in container with hx-swap-oob to replace the schedule list
    full_html = f'<div id="schedule-list" hx-swap-oob="innerHTML">{"".join(html_parts)}</div>'

    # Also include slip update via Alpine.js
    slip_script = f'<script>document.querySelector("[x-data]").__x.$data.slip = {slip};</script>'

    await manager.broadcast(full_html + slip_script)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time sync."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, receive any messages (we don't process them)
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

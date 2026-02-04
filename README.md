# coachella_set_schedule

A real-time schedule tracking application for festival stages. Operators can view scheduled act times and record actual start/end times. The system tracks "slip" (accumulated lateness) and syncs updates across all connected clients via WebSocket.

## Setup

```bash
# Create virtual environment
python3 -m venv venv

# Install dependencies
venv/bin/pip install -r requirements.txt
```

## Running the Server

```bash
# Start the server
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# Or with auto-reload for development
venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Access the app at http://localhost:8000

## Stopping the Server

```bash
# If running in foreground: Ctrl+C

# If running in background:
pkill -f "uvicorn main:app"
```

## Features

- Live clock display
- Slip tracking (accumulated lateness)
- Record actual start/end times for each act
- Real-time sync across multiple browser windows via WebSocket
- Dark theme UI

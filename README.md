# Festival Schedule Board

Real-time schedule tracking for festival stages. Operators record actual start/end times, the system tracks "slip" (accumulated lateness), and all connected clients stay in sync via WebSocket.

## Features

- **Live clock** with per-act `[Starts in X:XX]` countdowns
- **Slip tracking** — accumulated lateness propagates to downstream acts
- **Now Playing / Up Next banner** with live countdowns and overtime warnings
- **Record actual start/end times** for each act via operator controls
- **Real-time sync** across all clients via WebSocket (HTMX `hx-ws`)
- **View-only mode** (`/`) for spectators, **operator mode** (`/edit`) with full controls
- **Google Sheets integration** — reads schedule, writes actual times, polls every 30 seconds
- **Visual alerts** — flash warnings before act starts, danger styling when running overtime
- **Art-Net DMX integration** (optional) — reads 16-bit brightness from DMX and displays in UI
- **Hide/show completed acts** toggle
- **Time override** for testing — freeze the clock at a specific time in operator mode
- **Mobile-friendly dark theme** optimized for outdoor use
- **Docker support**

## Tech Stack

| Layer | Technology |
|-------|------------|
| Server | Python + FastAPI |
| Templates | Jinja2 (server-rendered HTML) |
| Interactivity | HTMX + Alpine.js (CDN, no build step) |
| Data | Google Sheets API (gspread + google-auth) |
| Real-time | WebSocket via HTMX ws extension |
| Optional | Art-Net DMX brightness listener |

## Setup

```bash
# Create virtual environment
python3 -m venv venv

# Install dependencies
venv/bin/pip install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env with your settings (see Configuration below)
```

## Running the Server

```bash
# Development (with auto-reload)
venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# Docker
docker build -t festival-schedule .
docker run -p 8000:8000 festival-schedule
```

Access the app:
- **View-only:** http://localhost:8000 — schedule display without controls
- **Operator:** http://localhost:8000/edit — full controls for recording times
- **LAN:** http://\<your-ip\>:8000

## Stopping the Server

```bash
# If running in foreground: Ctrl+C

# If running in background:
pkill -f "uvicorn main:app"
```

## Configuration

All settings via environment variables (`.env` file). See `.env.example` for the full template.

**Google Sheets:**
| Variable | Default | Description |
|----------|---------|-------------|
| `USE_GOOGLE_SHEETS` | `false` | Enable Google Sheets (false = mock data) |
| `GOOGLE_SHEETS_ID` | — | Spreadsheet ID from URL |
| `GOOGLE_SHEET_TAB` | — | Worksheet name (blank = first sheet) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | — | Path to service account JSON key |

**App:**
| Variable | Default | Description |
|----------|---------|-------------|
| `STAGE_NAME` | `Main Stage` | Display name shown in header |
| `TIMEZONE` | `America/Los_Angeles` | Festival local timezone |

**Art-Net DMX (optional):**
| Variable | Default | Description |
|----------|---------|-------------|
| `ARTNET_ENABLED` | `false` | Enable Art-Net UDP listener |
| `ARTNET_PORT` | `6454` | UDP port |
| `ARTNET_UNIVERSE` | `0` | DMX universe |
| `ARTNET_CHANNEL_HIGH` | `1` | High byte channel (16-bit brightness) |
| `ARTNET_CHANNEL_LOW` | `2` | Low byte channel |

## Google Sheets Setup

1. Create a Google Cloud project and enable the Sheets API
2. Create a service account and download the JSON key file
3. Share your spreadsheet with the service account email (editor access)
4. Set `USE_GOOGLE_SHEETS=true` in `.env` and fill in the sheet ID/tab/key path

**Expected sheet format** (header at row 5, data starts row 6):

| Column | Content |
|--------|---------|
| B | Artist name |
| D | Scheduled start (e.g. `14:30`) |
| E | Scheduled end |
| F | Actual time on (written by app) |
| G | Actual time off (written by app) |

The app polls Google Sheets every 30 seconds (configurable via `POLL_INTERVAL_SECONDS` in `main.py`) and broadcasts updates to all connected clients.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | View-only schedule page |
| `GET` | `/edit` | Operator schedule page |
| `POST` | `/acts/{name}/start` | Record actual start time |
| `POST` | `/acts/{name}/end` | Record actual end time |
| `POST` | `/acts/{name}/clear` | Clear actual times for an act |
| `POST` | `/api/reset` | Clear all actual times (testing) |
| `GET` | `/api/brightness` | Current Art-Net brightness value |
| `WS` | `/ws?mode=view\|edit` | WebSocket connection |

## Project Structure

```
coachella_set_schedule/
├── main.py              # FastAPI app, routes, WebSocket, background polling
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration
├── .env.example         # Environment variables template
├── app/
│   ├── config.py        # Settings from environment
│   ├── models.py        # Pydantic models (Act, Schedule)
│   ├── slip.py          # Slip calculation & formatting
│   ├── store.py         # In-memory mock data (development)
│   ├── sheets.py        # Google Sheets integration
│   ├── websocket.py     # WebSocket connection manager
│   └── artnet.py        # Art-Net DMX brightness listener
├── templates/
│   ├── base.html        # Base template (HTMX/Alpine.js CDN)
│   ├── index.html       # Main schedule view
│   └── components/
│       └── act_row.html # Single act row partial
└── static/
    └── styles.css       # Dark theme styles
```



## Development & Testing

**Mock data mode:** Set `USE_GOOGLE_SHEETS=false` to use in-memory sample data (8 acts, no external dependencies).

**Time override:** In operator mode, use the time input in the header to freeze the clock at a specific time. Click "Live" to resume real-time.

**Reset endpoint:** `POST /api/reset` clears all actual times and broadcasts the update — useful for demo resets between tests.

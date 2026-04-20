# Festival Schedule Board

Real-time schedule tracking for festival stages. Operators record actual start/end times, the system tracks "slip" (accumulated lateness), and all connected clients stay in sync via WebSocket.

## Features

- **Live clock** with per-act `[Starts in X:XX]` countdowns
- **Slip tracking** — accumulated lateness propagates to downstream acts
- **Now Playing / Up Next banner** with live countdowns and overtime warnings
- **Record actual start/end times** for each act via operator controls
- **Real-time sync** across all clients via WebSocket (HTMX `hx-ws`)
- **View-only mode** (`/`) for spectators, **operator mode** (`/edit`) with full controls
- **Stage display** (`/stage`) — large-format clock and up-next board for monitor at the stage
- **Google Sheets integration** — reads schedule, writes actual times, polls every 30 seconds
- **SQLite backend** — fully self-contained alternative to Sheets; schedules edited in-app via `/admin`
- **Schedule editor** (`/admin`) — create/edit/archive shows and individual acts without touching a spreadsheet
- **Show history** (`/history`) — slip/variance summary per show with per-act drill-down; CSV and JSON export
- **Visual alerts** — flash warnings before act starts, danger styling when running overtime
- **Art-Net DMX integration** (optional) — reads 16-bit brightness from DMX and displays in UI
- **Hide/show completed acts** toggle
- **Time override** for testing — freeze the clock at a specific time via `/preview`
- **Mobile-friendly dark theme** optimized for outdoor use
- **Docker support** with dev auto-reload mode



## Tech Stack

| Layer | Technology |
|-------|------------|
| Server | Python + FastAPI |
| Templates | Jinja2 (server-rendered HTML) |
| Interactivity | HTMX + Alpine.js (CDN, no build step) |
| Data | Google Sheets API _or_ SQLite (pluggable via `DATA_BACKEND`) |
| Real-time | WebSocket via HTMX ws extension |
| Database | SQLAlchemy + Alembic (SQLite backend) |
| Optional | Art-Net DMX brightness listener |



## Setup

### Docker Compose (recommended)

```bash
# Copy environment config and edit with your settings
cp .env.example .env

# Build and start
docker compose up --build
```

**Run on boot (auto-restart):**

The `docker-compose.yml` is configured with `restart: unless-stopped`, so the container will automatically restart on reboot or crash. You just need to ensure the Docker daemon itself starts on boot:

```bash
sudo systemctl enable docker
```

Then start the container once:

```bash
docker compose up -d
```

From that point on it will start automatically with the machine. It stays stopped only if you explicitly run `docker compose stop`.

To use Google Sheets, also mount your service account key:

```yaml
# in docker-compose.yml, under volumes:
- ./service-account.json:/app/service-account.json
```

Then set `GOOGLE_SERVICE_ACCOUNT_FILE=/app/service-account.json` in `.env`.



### Manual Setup (if not using Docker)

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
# Docker Compose (recommended)
docker compose up --build

# Docker Compose — dev mode on macOS (bridge networking + published port; no Art-Net)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# Docker Compose — dev mode on Linux (keeps host networking for Art-Net)
docker compose -f docker-compose.yml -f docker-compose.linux-dev.yml up

# Development without Docker (auto-reload)
venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production without Docker
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

Access the app:
- **View-only:** http://localhost:8000 — schedule display without controls
- **Operator:** http://localhost:8000/edit — full controls for recording times
- **Preview:** http://localhost:8000/preview — full controls plus a time-of-day input to freeze the clock at any point; use the **+24h** toggle to preview times past midnight
- **Stage display:** http://localhost:8000/stage — large-format current time and up-next board for a monitor at the stage
- **Schedule editor:** http://localhost:8000/admin — create/edit shows and acts (SQLite backend only; requires `EDIT_PASSWORD` if set)
- **History:** http://localhost:8000/history — slip/variance summary for all archived shows (requires `EDIT_PASSWORD` if set)
- **LAN:** http://\<your-ip\>:8000



## Stopping the Server

```bash
# If running in foreground: Ctrl+C

# If running in background:
pkill -f "uvicorn main:app"
```

## Configuration

All settings via environment variables (`.env` file). See `.env.example` for the full template.

**Data backend:**
| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_BACKEND` | `memory` | Store to use: `sheets`, `sqlite`, or `memory` |
| `SQLITE_PATH` | `./data/schedule.db` | SQLite DB file (when `DATA_BACKEND=sqlite`) |
| `ARCHIVE_RETENTION_COUNT` | `20` | Max archived shows to keep; oldest purged on advance |

### Data persistence (SQLite)

The SQLite DB is stored on the host at `./data/schedule.db` and bind-mounted into the container, so it survives container rebuilds, restarts, and `docker compose down` (including `down -v`). On startup the app runs idempotent Alembic migrations — the schema is never recreated.

**Things that actually remove data:**
- `rm data/schedule.db` on the host.
- Deleting a show from `/admin`.
- Automatic archive purge when more than `ARCHIVE_RETENTION_COUNT` shows (default 20) sit in the archive — oldest are pruned on `advance_show`.
- `POST /api/reset` clears recorded actual start/end times only; shows and scheduled times are preserved.

**Google Sheets** (when `DATA_BACKEND=sheets`):
| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_SHEETS_ID` | — | Spreadsheet ID from URL |
| `GOOGLE_SHEET_TAB` | — | Worksheet name (blank = first sheet) |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | — | Path to service account JSON key |
| `USE_GOOGLE_SHEETS` | `false` | _Deprecated._ Use `DATA_BACKEND=sheets` instead |

**App:**
| Variable | Default | Description |
|----------|---------|-------------|
| `STAGE_NAME` | `Main Stage` | Display name shown in header |
| `TIMEZONE` | `America/Los_Angeles` | Festival local timezone |

**Access control:**
| Variable | Default | Description |
|----------|---------|-------------|
| `EDIT_PASSWORD` | — | HTTP Basic Auth password for `/edit`, all `/admin*`, all `/history*`, and high-risk action endpoints. Leave empty to disable. |
| `PUBLIC_URL` | — | Cloudflare tunnel URL used in viewer QR code (e.g. `https://coachella.pickle.green`). Also editable at runtime via `/admin` when `DATA_BACKEND=sqlite`. |

**Art-Net DMX (optional):**
| Variable | Default | Description |
|----------|---------|-------------|
| `ARTNET_ENABLED` | `false` | Enable Art-Net UDP listener; brightness display is hidden in the UI when `false` |
| `ARTNET_PORT` | `6454` | UDP port |
| `ARTNET_UNIVERSE` | `0` | DMX universe |
| `ARTNET_CHANNEL_HIGH` | `1` | High byte channel (16-bit brightness) |
| `ARTNET_CHANNEL_LOW` | `2` | Low byte channel |

## Google Sheets Setup

1. Create a Google Cloud project and enable the Sheets API
2. Create a service account and download the JSON key file
3. Share your spreadsheet with the service account email (editor access)
4. Set `DATA_BACKEND=sheets` in `.env` and fill in the sheet ID/tab/key path

**Expected sheet format** (header at row 5, data starts row 6):

| Column | Content |
|--------|---------|
| C | Artist name |
| D | Scheduled start (e.g. `14:30`) |
| E | Scheduled end |
| F | Actual time on (written by app) |
| G | Actual time off (written by app) |
| H | Screentime total (written by app as `H:MM:SS`, On Deck rows only) |

Time values support `HH:MM`, `HH:MM:SS`, `H:MM AM/PM`, and `H:MM:SS AM/PM` formats.

> **Note:** Setlist items are displayed in the order they appear in the sheet, not sorted by time. Arrange rows in the sheet in the intended show order.

**Special row types:**

**Load In rows** — any row whose name contains `Load In` (e.g. `Load In - Main Stage`):
- Displayed as an informational label with no operator buttons
- Automatically hidden 1 hour after their scheduled start time
- No actual time recording; column E (scheduled end) is not required

**On Deck rows** — any row whose name contains `On Deck` (e.g. `On Deck - Missy Elliot`):
- Display a live screentime counter (MM:SS) instead of set start/end buttons
- Operators use **START Screentime** / **STOP Screentime** buttons to track how long an act is visible on screen before going on
- Accumulated screentime is written to column H in `H:MM:SS` format each time the session is stopped, and also synced every 30 seconds while a session is active
- **Column E (scheduled end) is required** — the row is automatically hidden once local time passes this value
- Multiple start/stop cycles accumulate (total is preserved across sessions)

The app polls Google Sheets every 30 seconds (configurable via `POLL_INTERVAL_SECONDS` in `main.py`) and broadcasts updates to all connected clients.

## API Endpoints

**Pages:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/` | — | View-only schedule page |
| `GET` | `/edit` | password | Operator schedule page |
| `GET` | `/preview` | — | Operator page with time-of-day override input and +24h toggle |
| `GET` | `/stage` | — | Large-format stage display (current time + up-next) |
| `GET` | `/admin` | password | Schedule editor — list/create/archive shows (SQLite only) |
| `GET` | `/admin/shows/{id}` | password | Show detail — add/edit/reorder acts |
| `GET` | `/history` | password | Slip/variance summary for all archived shows |
| `GET` | `/history/{id}` | password | Per-act drill-down for a single show |

**Operator actions:**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/acts/{name}/start` | — | Record actual start time |
| `POST` | `/acts/{name}/end` | — | Record actual end time |
| `POST` | `/acts/{name}/clear` | — | Clear actual times for an act |
| `POST` | `/api/reset` | password | Clear all actual times |
| `POST` | `/api/reload` | password | Force all connected clients to hard-reload the page |
| `POST` | `/api/show/advance` | password | Advance to next show tab |
| `POST` | `/api/recording/toggle` | password | Toggle automatic recording triggers on/off |

**Export (SQLite only):**
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/admin/shows/{id}/export.json` | password | Export show as JSON |
| `GET` | `/admin/shows/{id}/export.csv` | password | Export show as CSV |

**Read-only / polling (always public):**
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/brightness` | Current Art-Net brightness value |
| `GET` | `/api/kipro/status` | Ki Pro transport state |
| `GET` | `/api/weather` | WeatherLink proxy |
| `WS` | `/ws?mode=view\|edit` | WebSocket connection |

## Project Structure

```
coachella_set_schedule/
├── main.py              # FastAPI app, routes, WebSocket, background polling
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration
├── docker-compose.yml       # Docker Compose configuration
├── docker-compose.dev.yml       # Dev override (macOS): bridge net + published port + auto-reload
├── docker-compose.linux-dev.yml # Dev override (Linux): host net for Art-Net + auto-reload
├── alembic.ini          # Alembic migration config
├── alembic/
│   ├── env.py           # Alembic environment (connects to SQLite)
│   └── versions/
│       ├── 0001_initial.py         # Initial schema (Show, Act, RecordingEvent)
│       ├── 0002_act_category.py    # Act.category column
│       └── 0003_app_settings.py    # AppSetting key/value table
├── .env.example         # Environment variables template
├── app/
│   ├── config.py        # Settings from environment
│   ├── models.py        # Pydantic models (Act, Schedule) — boundary type between store and app
│   ├── slip.py          # Slip calculation & formatting
│   ├── store.py         # In-memory mock data (development / memory backend)
│   ├── sheets.py        # Google Sheets integration (sheets backend)
│   ├── sqlite_store.py  # SQLite backend (implements same interface as store.py/sheets.py)
│   ├── db/
│   │   ├── engine.py    # SQLAlchemy engine + init_db() (runs Alembic migrations on startup)
│   │   └── models.py    # SQLAlchemy ORM models (Show, Act, RecordingEvent, AppSetting)
│   ├── websocket.py     # WebSocket connection manager
│   ├── artnet.py        # Art-Net DMX brightness listener (optional)
│   ├── recorder.py      # AJA Ki Pro HTTP commands (record/stop/status)
│   ├── triggers.py      # Schedule-based recording trigger engine
│   ├── ntfy.py          # ntfy.sh push notification sender
│   ├── notifier.py      # Schedule-based and action-based ntfy notifications
│   └── companion.py     # Bitfocus Companion HTTP button-press integration
├── templates/
│   ├── base.html        # Base template (HTMX/Alpine.js CDN)
│   ├── index.html       # Main schedule view
│   ├── stage.html       # Large-format stage display
│   ├── history.html     # Show history list (slip/variance summary)
│   ├── history_detail.html # Per-show act drill-down
│   ├── admin/
│   │   ├── shows.html       # /admin — show list, create, archive, QR settings
│   │   └── show_detail.html # /admin/shows/{id} — act editor
│   └── components/
│       ├── act_row.html     # Single act row partial
│       └── app_nav.html     # Unified top nav (rendered on /edit, /admin, /history)
├── static/
│   ├── styles.css           # Dark theme styles
│   └── schedule_utils.js    # Shared JS helpers loaded by base.html (timeToSeconds, normalizeActTimes, formatCountdown)
└── tests/
    ├── test_models.py         # Act model computed fields
    ├── test_slip.py           # Slip calculation unit tests
    ├── test_midnight.py       # Midnight rollover tests
    ├── test_api.py            # HTTP endpoint behaviour
    ├── test_api_auth.py       # Auth gating tests (EDIT_PASSWORD enforcement)
    ├── test_store.py          # In-memory store operations
    ├── test_sqlite_store.py   # SQLite store operations
    ├── test_slip_summary.py   # Slip/variance summary logic
    └── ...                    # Sheets parsing, screentime, trigger tests
```

## Development & Testing

**Mock data mode:** Set `DATA_BACKEND=memory` to use in-memory sample data (8 acts, no external dependencies).

**Time override:** On `/preview`, use the time input in the header to freeze the clock at a specific time. Toggle **+24h** to simulate times past midnight (e.g. enter `01:30` and toggle +24h to preview 1:30am). Click "Live" to resume real-time.

**Reset endpoint:** `POST /api/reset` clears all actual times and broadcasts the update — useful for demo resets between tests. Disabled (button greyed out) when `DATA_BACKEND=sheets`.

**Force client reload:** `POST /api/reload` broadcasts a hard-reload command to every connected browser tab via WebSocket. Useful after a container rebuild to ensure all clients pick up new CSS/JS without manually refreshing. Static files are also cache-busted by app version (`styles.css?v=X.X.X`) so bumping `VERSION` + rebuilding guarantees fresh assets.

```bash
curl -X POST http://localhost:8000/api/reload
# or on LAN:
curl -X POST http://<your-ip>:8000/api/reload
```

**Rec Triggers toggle:** The **Rec Triggers** button on `/edit` enables or disables automatic time recording triggers.

## Running Tests

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run a specific test file
python -m pytest tests/test_midnight.py -v

# Run tests matching a keyword
python -m pytest -k "midnight" -v
```

Tests use no external dependencies — no Google Sheets connection required. `conftest.py` sets `DATA_BACKEND=memory` and leaves `EDIT_PASSWORD` empty. The test suite covers:

| File | What it tests |
|------|--------------|
| `test_models.py` | Act model computed fields (duration, variance, state) |
| `test_slip.py` | Slip calculation and formatting |
| `test_midnight.py` | Midnight rollover: duration, variance, and slip across day boundaries |
| `test_api.py` | HTTP endpoint behaviour |
| `test_api_auth.py` | EDIT_PASSWORD enforcement on gated routes |
| `test_store.py` | In-memory store operations |
| `test_sqlite_store.py` | SQLite store CRUD and show lifecycle |
| `test_slip_summary.py` | Slip/variance summary computed values |
| `test_sheets_*.py` | Google Sheets parsing, formatting, and caching logic |
| `test_triggers.py` | Recording trigger engine (normalization, midnight, skips) |

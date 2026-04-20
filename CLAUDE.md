# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Festival Schedule Board - a real-time schedule tracking application for festival stages. Operators can view scheduled act times and record actual start/end times. The system tracks "slip" (accumulated lateness) and projects impacts on downstream acts.

Key domain concepts:
- **Slip**: Signed value (positive = late, negative = early) representing how far the live timeline is vs published schedule
- **Projections**: Always slip-aware, never pull times earlier than scheduled
- **Breaks**: Time between acts; early finishes extend breaks, late finishes compress them

## Architecture

| Layer | Technology |
|-------|------------|
| Server | Python + FastAPI (single process) |
| Templates | Jinja2 (server-rendered HTML) |
| Interactivity | HTMX (server interactions, WebSocket) + Alpine.js (client-side reactivity) |
| Data | Google Sheets API (Service Account auth) |
| Hosting | Local machine, LAN access only |

No build step required - HTMX and Alpine.js loaded via CDN script tags.

### Data Flow
1. FastAPI renders schedule page via Jinja2 templates
2. HTMX WebSocket (`hx-ws`) keeps all operators in sync
3. "Record Now" button sends time via HTMX, FastAPI broadcasts to all clients
4. Alpine.js handles live clock, computed slip values, per-act countdowns, and act alerts client-side
5. Actual times written to the active backend (Google Sheets or SQLite) for persistence
6. Background task polls the active backend every 30 seconds and broadcasts updates to all clients

### Google Sheet Schema

The app reads data by column position (not header names) to handle sheets with non-standard headers:

| Column | Position | Description |
|--------|----------|-------------|
| Artist name | C (col 3) | Artist/act name |
| Scheduled start | D (col 4) | Published start time (e.g., `14:30`) |
| Scheduled end | E (col 5) | Published end time |
| Actual time on | F (col 6) | Recorded start time (filled by app) |
| Actual time off | G (col 7) | Recorded end time (filled by app) |
| Screentime total | H (col 8) | On Deck screentime written as `H:MM:SS` (filled by app) |

Header row is expected at row 5, data starts at row 6. Rows without a valid `scheduled_start` are skipped; `scheduled_end` is optional — acts with no end time (e.g. final headliner) are allowed through and handled gracefully. Time values are parsed flexibly and support `HH:MM`, `HH:MM:SS`, `H:MM AM/PM`, and `H:MM:SS AM/PM` formats. **END OF SHOW rows** need no time — the parser infers the start time from the previous act's `scheduled_end`. If no time is available (e.g. the last act had no `scheduled_end`), the END OF SHOW row is included with no scheduled time and only triggers the end-of-show state once the operator marks the last act complete.

## MVP Scope

**Included:** Single stage, schedule display, actual time recording, slip tracking, WebSocket sync between operators

**Excluded:** Multi-stage support, artist photos, cloud hosting

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload enabled)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
python -m pytest
python -m pytest -v                        # verbose
python -m pytest tests/test_midnight.py   # specific file
python -m pytest -k "midnight"            # by keyword

# Access the app
# View-only:    http://localhost:8000
# Operator:     http://localhost:8000/edit
# Preview:      http://localhost:8000/preview  (operator + time-of-day override, +24h toggle for post-midnight)
# Stage board:  http://localhost:8000/stage    (large-format clock + up-next display)
# Schedule editor: http://localhost:8000/admin (SQLite only; gated by EDIT_PASSWORD)
# History:      http://localhost:8000/history  (slip/variance; gated by EDIT_PASSWORD)
# LAN: http://<your-ip>:8000

# Force all connected browser tabs to hard-reload (useful after a container rebuild)
curl -X POST http://localhost:8000/api/reload
```

## Project Structure

```
coachella_set_schedule/
├── main.py              # FastAPI app entry point, background polling
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
├── VERSION              # App version string (e.g. 1.3.0), read at startup
├── alembic.ini          # Alembic migration config
├── alembic/
│   ├── env.py           # Alembic environment (connects to SQLite)
│   └── versions/
│       ├── 0001_initial.py         # Initial schema (Show, Act, RecordingEvent)
│       ├── 0002_act_category.py    # Act.category column
│       └── 0003_app_settings.py    # AppSetting key/value table
├── app/
│   ├── config.py        # Settings from environment (includes APP_VERSION, WEATHER_URL, ARCHIVE_RETENTION_COUNT)
│   ├── models.py        # Pydantic models (Act, Schedule) — boundary type; effective_category is the canonical accessor
│   ├── slip.py          # Slip calculation logic
│   ├── store.py         # In-memory mock data (memory backend)
│   ├── sheets.py        # Google Sheets integration (column-based parsing; sheets backend)
│   ├── sqlite_store.py  # SQLite backend (same interface as store.py/sheets.py)
│   ├── db/
│   │   ├── engine.py    # SQLAlchemy engine + init_db() (runs Alembic upgrade head on startup)
│   │   └── models.py    # SQLAlchemy ORM models (Show, Act, RecordingEvent, AppSetting)
│   ├── websocket.py     # WebSocket connection manager
│   ├── artnet.py        # Art-Net brightness listener (optional; brightness display hidden when ARTNET_ENABLED=false)
│   ├── recorder.py      # AJA Ki Pro HTTP commands (record/stop/status)
│   ├── triggers.py      # Schedule-based recording trigger engine
│   ├── ntfy.py          # ntfy.sh push notification sender
│   ├── notifier.py      # Schedule-based and action-based ntfy notifications
│   └── companion.py     # Bitfocus Companion HTTP button-press integration
├── templates/
│   ├── base.html        # Base template with HTMX/Alpine.js; renders version footer and show name label
│   ├── index.html       # Main schedule view
│   ├── stage.html       # Large-format stage display (/stage)
│   ├── history.html     # Show history list — slip/variance summary (/history)
│   ├── history_detail.html # Per-show per-act drill-down (/history/{id})
│   ├── admin/
│   │   ├── shows.html       # /admin — show list, archive controls, QR settings editor
│   │   └── show_detail.html # /admin/shows/{id} — act CRUD, actual-times visibility, export buttons
│   └── components/
│       ├── act_row.html     # Single act row partial
│       └── app_nav.html     # Unified top nav (rendered when show_nav=True: /edit, /admin, /history)
├── static/
│   ├── styles.css           # Dark theme styles
│   └── schedule_utils.js    # Shared JS helpers: timeToSeconds, normalizeActTimes, formatCountdown
└── tests/
    ├── test_models.py        # Act model unit tests
    ├── test_slip.py          # Slip calculation unit tests
    ├── test_midnight.py      # Midnight rollover tests
    ├── test_triggers.py      # Recording trigger engine tests (normalization, midnight, skips)
    ├── test_sqlite_store.py  # SQLite store CRUD and show lifecycle
    ├── test_slip_summary.py  # Slip/variance summary computed values
    ├── test_api_auth.py      # EDIT_PASSWORD enforcement on gated routes
    └── ...                   # API, store, and sheets tests
```

## Data Backends

The app supports three pluggable backends, selected at startup via `DATA_BACKEND`:

| Value | Description |
|-------|-------------|
| `sheets` | Google Sheets (requires service account + sheet ID). Historical default. |
| `sqlite` | Internal SQLite DB at `SQLITE_PATH` (default `./data/schedule.db`). Schedules edited in-app via `/admin`. Alembic migrations run on startup. |
| `memory` | In-process mock data. Resets on restart. Dev only. |

`USE_GOOGLE_SHEETS=true` is deprecated; when `DATA_BACKEND` is unset it falls back to `sheets` if `USE_GOOGLE_SHEETS=true`, otherwise `memory`.

### Switching to Google Sheets
1. Copy `.env.example` to `.env` and fill in your values
2. Set `DATA_BACKEND=sheets` in `.env`
3. Configure `GOOGLE_SHEETS_ID`, `GOOGLE_SHEET_TAB`, and `GOOGLE_SERVICE_ACCOUNT_FILE`

### Switching to SQLite
1. Set `DATA_BACKEND=sqlite` in `.env`
2. (Optional) Set `SQLITE_PATH` to change the DB file location
3. On first start, Alembic creates the schema. Use `/admin` to create a show and add acts.

### SQLite persistence

The SQLite file lives on the **host** at `./data/schedule.db`, bind-mounted into the container at `/app/data` (`docker-compose.yml:10`, plus matching mounts in both dev overrides). Container rebuilds don't touch it.

- `init_db()` (`app/db/engine.py:46-64`) runs `alembic upgrade head` on startup. Migrations are idempotent — the schema is never dropped or recreated, only upgraded.
- **Survives:** `docker compose up --build`, `docker compose restart`, `docker compose down`, even `docker compose down -v` (bind mounts to host paths ignore `-v`).
- **Wipes data:**
  - `rm data/schedule.db` on the host (or wiping `./data/`).
  - Clicking **Delete** on a show in `/admin`.
  - Archive auto-purge when the archive grows past `ARCHIVE_RETENTION_COUNT` (default 20) — oldest archived shows are pruned on `advance_show`.
  - `POST /api/reset` — note this only clears actual start/end times on acts; it does **not** remove shows or scheduled times.

`.db-journal` files next to the DB (SQLite WAL/journal) are transient and safe to ignore; `.gitignore` already excludes `data/*.db*`.

**Show name in header** — `main.py` injects `current_show` into all page template contexts. When `DATA_BACKEND=sqlite`, this is the name of the active show record; when `DATA_BACKEND=sheets`, it is the active sheet tab name. `base.html` renders it as a small label below the stage name. `/` and `/stage` display it; it is also visible on `/edit` and `/admin`.

The app polls the active backend every 30 seconds (configurable via `POLL_INTERVAL_SECONDS` in `main.py`) and broadcasts updates to all connected clients.

**Multi-show tabs:** Set `SHOW_TABS` to a comma-separated list of sheet tab names (e.g. `W1Shw1,W1Shw2,W2Shw4`). The app starts on the tab named by `GOOGLE_SHEET_TAB`; if that tab is not in the list, it defaults to the first tab. Operators advance to the next show via the "Advance to Next Show" button on `/edit`, which reloads all clients.

## Key Business Rules

- Published schedule (`scheduled_start`/`scheduled_end`) is authoritative and never auto-modified
- Early finishes do NOT pull next act earlier - they extend break time
- Late finishes create slip that propagates downstream
- Slip formula: `projected_start[i] = scheduled_start[i] + slip`
- Conflict resolution: last-write-wins with timestamp
- Timezone: Festival local time only (PDT for Coachella)
- **Midnight rollover:** Acts past midnight (e.g. `01:00`) are stored as plain `time` objects; rollover is handled at comparison time. Server-side: `models.py` adds `timedelta(days=1)` when end < start. Client-side: `normalizeActTimes()` walks acts in sheet order and bumps any time that drops more than 1 hour below the previous act's time. Acts must be in chronological order in the sheet for this to work correctly. The trigger engine (`triggers.py`) applies the same normalization via `_normalize_act_start_secs()`. Both use a **5am reset threshold**: times before 5am on a midnight-crossing show are treated as same-show (next-day) time; after 5am the schedule resets to normal day context.
- **END OF SHOW row:** A sheet row whose artist name is exactly `END` or `END OF SHOW` (case-insensitive) marks the end of the show. The `is_end_of_show` computed field on `Act` identifies these rows. They require no scheduled time — the parser infers one from the previous act's `scheduled_end`. If the END OF SHOW row has no scheduled time (e.g. last act has no `scheduled_end`), the banner switches to "END OF SHOW / Have a Great Night" only once the operator marks the last act complete. The loop stops at END OF SHOW and never processes acts below it in the sheet.
- **Acts with no `scheduled_end`:** Allowed through the parser. Client-side null guards prevent NaN countdowns and false `act-missed` states. While the last act is live, a secondary "Show ends in X:XX" countdown appears in the now-playing card if an END OF SHOW row with a scheduled time follows it.
- **Special row types** — the `Act.category` field (`set` | `loadin` | `ondeck` | `changeover` | `preshow` | `end`) is the authoritative row-type marker when set (SQLite backend). The `effective_category` property falls back to name-based detection when `category` is `None` (Sheets and memory backends). The `is_*` computed properties read from `effective_category`. Always branch on `effective_category` or the `is_*` properties — never on `act.category` directly.
  - `is_loadin` — name contains `'load in'`: informational label, no buttons, auto-hidden 1 hour after scheduled start
  - `is_ondeck` — name contains `'on deck'` **or** `'stage time'`: shows screentime counter + START/STOP Screentime buttons; no set-start/stop buttons
  - `is_changeover` — name contains `'changeover'`: no recording trigger fired
  - `is_preshow` — name contains `'preshow'`: no recording trigger, no set buttons
  - `is_end_of_show` — name is exactly `'end'` or `'end of show'` (case-insensitive): end-of-show banner trigger

## Client-Side Timer Architecture

The `updateTime()` method runs every second and is the single entry point for all per-tick logic. It queries `.act-row` elements once, parses their `data-*` attributes into a shared `acts` array, then passes `(currentSecs, acts)` to:
- `calculateSlip()` — computes accumulated slip from actual vs scheduled times
- `checkActAlerts()` — applies flash/warning CSS classes; suppresses `flash-warning` on act rows when the up-next section is already pulsing (act starting within 2 minutes) to avoid competing animations
- `updateNowPlaying()` — renders the now-playing/up-next banner; adds `starting-soon` pulse class when next act is ≤2 minutes away; updates countdown text in-place to avoid restarting CSS animations. The **Up Next** card only appears if the show is already underway (any act completed) or the next act starts within 60 minutes — prevents showing a distant first act at 8am. When an END OF SHOW row is reached in the sheet loop, the banner switches to the **END OF SHOW / Have a Great Night** card and no acts below it are considered.
- `updateCountdowns()` — shows `[Starts in X:XX]` for future acts, hidden once started or past scheduled time
- `updateOnDeckRows()` — adds `act-complete` to On Deck rows once local time passes their `scheduled_end`, hiding them via the same `hide-completed` mechanism as regular acts
- `updateLoadInRows()` — adds `act-complete` to Load In rows 1 hour after their `scheduled_start`

`updateNowPlaying()` also does a second pass after the main loop: if a now-playing act is found, it scans forward to find whether the next item is an END OF SHOW row with a scheduled time, and if so renders a `.np-eos-wrap` secondary countdown ("Show ends in X:XX") inside the now-playing card.

After WebSocket HTML swaps (from Google Sheets polling), `htmx:wsAfterMessage` triggers `updateTime()` to immediately re-apply countdowns and alerts before the browser paints. Use `htmx:wsAfterMessage` (not `htmx:afterSwap` or `htmx:afterSettle`) for flicker-free post-swap updates.

The time-of-day override (`timeOverride` / `frozenTime`) is only surfaced on `/preview`. It freezes `currentTime` to a fixed value so operators can inspect how the page renders at any point in the schedule without waiting for real time to advance. A `+24h` toggle adds 86400 seconds to `currentSecs` (without changing the displayed time string) to simulate post-midnight viewing.

## Versioning

The app version is stored in the `VERSION` file at the repo root. It is read at startup in `app/config.py` into `APP_VERSION` and injected into every template context as `app_version`. The version is displayed subtly in the footer of every page (`base.html`). To bump the version, edit the `VERSION` file and restart the server.

## AJA Ki Pro Integration

Set `KIPRO_IP` in `.env` to enable. The app communicates with the Ki Pro via its HTTP API (`/config?action=...`).

- **Automatic triggers** — `app/triggers.py` fires `start_recording()` a configurable number of minutes before a scheduled act start. Toggled live via the "Rec Triggers: ON/OFF" button on `/edit`. Trigger windows are computed using `_normalize_act_start_secs()` so midnight-crossing shows work correctly without modulo arithmetic.
- **Deck status + record/stop button** — `/edit` shows a single combined circular button in the schedule header (only when `KIPRO_IP` is set). On desktop it is a combined widget; on touch devices (`pointer: coarse`) it splits into a separate status dot and a plain record/stop button to avoid iOS rendering issues with `::after` pseudo-elements on buttons. States: red outer + pulsing green/red inner dot = ready to record; red pulsing square inside = rolling; gray dimmed = unreachable/disabled.
- **Transport state polling** — the frontend polls `GET /api/kipro/status` every 5 seconds. This queries `eParamID_TransportState` on the Ki Pro; value `"2"` = recording. The REC banner in `/edit` is driven by this actual deck state (not just trigger state). If the deck is rolling with no active trigger, a generic "Deck Rolling" banner is shown.
- **Manual API endpoints** — `POST /api/kipro/record` and `POST /api/kipro/stop` send commands directly to the deck.

The transport state record value is `_STATE_RECORD = "2"` in `app/recorder.py` — adjust if your Ki Pro model returns a different value.

## ntfy.sh Push Notifications

Set `NTFY_URL` in `.env` (e.g. `https://ntfy.sh/your-topic`) to enable push notifications. All sends are fire-and-forget in daemon threads; everything silently no-ops if `NTFY_URL` is unset.

Notifications fired by `app/notifier.py`:

| Event | Title | Priority |
|-------|-------|----------|
| ~5 min before scheduled start | "Starting in ~5 min: {act}" | high |
| ~10 min before scheduled end (act live) | "Ending in ~10 min: {act}" | high |
| Operator marks set start | "Set started: {act}" | default |
| Operator marks set complete | "Set complete: {act}" | default |

Time-based notifications are checked each poll cycle (every 30s). A 45-second window is used to ensure the notification fires within one cycle of the target time. Each act fires each notification type at most once per server session.

## WeatherLink Weather Display

Set `WEATHER_URL` in `.env` to a WeatherLink embeddable getData endpoint to enable live weather in the header. Leave empty to hide the weather display entirely.

- **Endpoint format** — `https://www.weatherlink.com/embeddablePage/getData/{embeddable-page-id}`
- **Displayed fields** — temperature (°F), wind speed + direction, gusts
- **"As of" timestamp** — `lastReceived` from the API, formatted as `M/D H:MMam/pm` in the configured timezone
- **Poll interval** — every 3 minutes client-side via `pollWeather()` in `index.html`
- **Backend proxy** — `GET /api/weather` in `main.py` fetches WeatherLink and returns a cleaned subset of fields; all network errors are silently swallowed
- **Placement** — header left column, below the "Live Data" server status indicator

## Bitfocus Companion Integration

Set `COMPANION_URL` in `.env` (e.g. `http://192.168.1.100:19267`) to enable Companion button presses. All calls are fire-and-forget in daemon threads; everything silently no-ops if `COMPANION_URL` is unset.

`app/companion.py` exposes two functions called from the operator mark-start/stop endpoints in `main.py`:

| Operator action | Companion call | Button |
|---|---|---|
| Mark Set Start (`POST /acts/{name}/start`) | `trigger_set_mv_rec()` | Page 15, Row 3, Col 4 |
| Mark Set Stop (`POST /acts/{name}/end`) | `trigger_changeover_rec()` | Page 15, Row 3, Col 2 |

## Access Control & Public URL

- **Edit page auth** — Set `EDIT_PASSWORD` in `.env` to enable HTTP Basic Auth on `GET /edit`, all `/admin*` routes, `/history*`, and four high-risk action endpoints (`POST /api/reset`, `/api/reload`, `/api/show/advance`, `/api/recording/toggle`). The browser prompts once per session; only the password is checked (username ignored). Leave empty to disable (LAN-only use). Per-act endpoints (`/acts/{name}/*`) and deck control (`/api/kipro/*`) are intentionally left ungated so curl-based automation keeps working. Read-only polling endpoints (`/api/time`, `/api/weather`, `/api/brightness`, `/api/kipro/status`) are always public because the viewer pages depend on them.
- **Public URL / QR code** — Set `PUBLIC_URL` in `.env` (e.g. `https://coachella.pickle.green`) to specify the Cloudflare tunnel address used in the viewer QR code. Falls back to `window.location.origin` if unset. When `DATA_BACKEND=sqlite`, the QR URL and visibility can also be edited at runtime via the `/admin` settings panel (stored in the `app_settings` table as `qr_url` and `qr_enabled`); `.env` is used only as the first-run seed. The QR button appears in the schedule header on all pages and generates the code client-side via `qrcodejs`.
- **Cloudflare CSS caching** — Cloudflare aggressively caches static assets. After a Docker rebuild that changes CSS or JS, purge the cache via Cloudflare dashboard → Caching → Configuration → Purge Everything. When debugging mobile-only style issues, always test via LAN IP first to rule out CDN caching before assuming a code bug.

## Startup Auto-Reload

Set `AUTO_RELOAD_ON_STARTUP=true` in `.env` to broadcast a hard-reload to all connected clients after server startup (default delay: 15 seconds). Ensures browser tabs pick up new HTML/CSS/JS after a container rebuild without manual intervention. Delay is configurable via `STARTUP_RELOAD_DELAY`. Leave disabled (`false`) in dev to avoid tab thrashing during `--reload` development.

## Offline Resilience

The app continues to function client-side if the server goes down after the page has loaded — Alpine.js keeps running the clock and all calculations using the last received schedule state. Two mechanisms protect against accidental data loss:

- **Server status indicator** — "Live Data" (green) / "Offline Data" (red) shown under the stage name, driven by `htmx:wsOpen` / `htmx:wsClose` events
- **`beforeunload` warning** — browser confirmation dialog fires if the user tries to close or refresh while offline
- **`overscroll-behavior: none`** — prevents pull-to-refresh on mobile

Note: a service worker cache was considered but removed — service workers require HTTPS, and this app runs over plain HTTP on LAN.

## Mobile Responsive Behavior

Two CSS media queries handle mobile layout in `static/styles.css`:

- **`@media (max-width: 640px)`** — small screen layout adjustments (padding, font sizes, flex stacking). Does NOT apply to iPhones in landscape or larger phones.
- **`@media (pointer: coarse)`** — touch device targeting regardless of screen size. Used for: hiding "Advance to Next Show" button, enabling `flex-wrap` on the schedule header so buttons don't overflow, shrinking label/button text, and splitting the combined Ki Pro deck button into separate status dot + record button (avoids iOS `::after` pseudo-element rendering issues on `<button>` elements).

When adding mobile-specific styles, prefer `pointer: coarse` over `max-width` breakpoints — it reliably targets phones and tablets at any orientation.

The app is also accessible externally via a Cloudflare tunnel (`PUBLIC_URL`). The `/edit` page is password-protected when `EDIT_PASSWORD` is set.

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
5. Actual times written to Google Sheets for persistence
6. Background task polls Google Sheets every 30 seconds and broadcasts updates to all clients

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
├── VERSION              # App version string (e.g. 1.0.9), read at startup
├── app/
│   ├── config.py        # Settings from environment (includes APP_VERSION, WEATHER_URL)
│   ├── models.py        # Pydantic models (Act, Schedule)
│   ├── slip.py          # Slip calculation logic
│   ├── store.py         # In-memory mock data (development)
│   ├── sheets.py        # Google Sheets integration (column-based parsing)
│   ├── websocket.py     # WebSocket connection manager
│   ├── artnet.py        # Art-Net brightness listener (optional)
│   ├── recorder.py      # AJA Ki Pro HTTP commands (record/stop/status)
│   ├── triggers.py      # Schedule-based recording trigger engine
│   ├── ntfy.py          # ntfy.sh push notification sender
│   └── notifier.py      # Schedule-based and action-based ntfy notifications
├── templates/
│   ├── base.html        # Base template with HTMX/Alpine.js; renders version footer
│   ├── index.html       # Main schedule view
│   ├── stage.html       # Large-format stage display (/stage)
│   └── components/
│       └── act_row.html # Single act row partial
├── static/
│   ├── styles.css           # Dark theme styles
│   └── schedule_utils.js    # Shared JS helpers: timeToSeconds, normalizeActTimes, formatCountdown
└── tests/
    ├── test_models.py        # Act model unit tests
    ├── test_slip.py          # Slip calculation unit tests
    ├── test_midnight.py      # Midnight rollover tests
    ├── test_triggers.py      # Recording trigger engine tests (normalization, midnight, skips)
    └── ...                   # API, store, and sheets tests
```

## Switching to Google Sheets

To use Google Sheets instead of mock data:
1. Copy `.env.example` to `.env` and fill in your values
2. Set `USE_GOOGLE_SHEETS=true` in `.env`
3. Configure `GOOGLE_SHEETS_ID`, `GOOGLE_SHEET_TAB`, and `GOOGLE_SERVICE_ACCOUNT_FILE`

The app polls Google Sheets every 30 seconds (configurable via `POLL_INTERVAL_SECONDS` in `main.py`) and broadcasts updates to all connected clients.

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
- **Manual record/stop buttons** — `/edit` shows a red record button and a stop button in the schedule header (only when `KIPRO_IP` is set). Only one is visible at a time, toggled by the actual deck state.
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

## Access Control & Public URL

- **Edit page auth** — Set `EDIT_PASSWORD` in `.env` to enable HTTP Basic Auth on `GET /edit`. The browser prompts once per session. Only the password is checked; the username field is ignored. Leave empty to disable (LAN-only use).
- **Public URL / QR code** — Set `PUBLIC_URL` in `.env` (e.g. `https://coachella.pickle.green`) to specify the Cloudflare tunnel address used in the viewer QR code. Falls back to `window.location.origin` if unset. The QR button appears in the schedule header on all pages and generates the code client-side via `qrcodejs`.

## Startup Auto-Reload

Set `AUTO_RELOAD_ON_STARTUP=true` in `.env` to broadcast a hard-reload to all connected clients after server startup (default delay: 15 seconds). Ensures browser tabs pick up new HTML/CSS/JS after a container rebuild without manual intervention. Delay is configurable via `STARTUP_RELOAD_DELAY`. Leave disabled (`false`) in dev to avoid tab thrashing during `--reload` development.

## Offline Resilience

The app continues to function client-side if the server goes down after the page has loaded — Alpine.js keeps running the clock and all calculations using the last received schedule state. Two mechanisms protect against accidental data loss:

- **Server status indicator** — "Live Data" (green) / "Offline Data" (red) shown under the stage name, driven by `htmx:wsOpen` / `htmx:wsClose` events
- **`beforeunload` warning** — browser confirmation dialog fires if the user tries to close or refresh while offline
- **`overscroll-behavior: none`** — prevents pull-to-refresh on mobile

Note: a service worker cache was considered but removed — service workers require HTTPS, and this app runs over plain HTTP on LAN.

The app is also accessible externally via a Cloudflare tunnel (`PUBLIC_URL`). The `/edit` page is password-protected when `EDIT_PASSWORD` is set.

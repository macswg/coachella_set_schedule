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
| Artist name | B (col 2) | Artist/act name |
| Scheduled start | D (col 4) | Published start time (e.g., `14:30`) |
| Scheduled end | E (col 5) | Published end time |
| Actual time on | F (col 6) | Recorded start time (filled by app) |
| Actual time off | G (col 7) | Recorded end time (filled by app) |
| Screentime total | H (col 8) | On Deck screentime written as `H:MM:SS` (filled by app) |

Header row is expected at row 5, data starts at row 6. Rows without valid scheduled start/end times are skipped. **On Deck rows must have a `scheduled_end`** — this is used to auto-hide the row once local time passes that value. Time values are parsed flexibly and support `HH:MM`, `HH:MM:SS`, `H:MM AM/PM`, and `H:MM:SS AM/PM` formats.

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
```

## Project Structure

```
coachella_set_schedule/
├── main.py              # FastAPI app entry point, background polling
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
├── app/
│   ├── config.py        # Settings from environment
│   ├── models.py        # Pydantic models (Act, Schedule)
│   ├── slip.py          # Slip calculation logic
│   ├── store.py         # In-memory mock data (development)
│   ├── sheets.py        # Google Sheets integration (column-based parsing)
│   ├── websocket.py     # WebSocket connection manager
│   └── artnet.py        # Art-Net brightness listener (optional)
├── templates/
│   ├── base.html        # Base template with HTMX/Alpine.js
│   ├── index.html       # Main schedule view
│   ├── stage.html       # Large-format stage display (/stage)
│   └── components/
│       └── act_row.html # Single act row partial
├── static/
│   └── styles.css       # Dark theme styles
└── tests/
    ├── test_models.py        # Act model unit tests
    ├── test_slip.py          # Slip calculation unit tests
    ├── test_midnight.py      # Midnight rollover tests
    └── ...                   # API, store, and sheets tests
```

## Switching to Google Sheets

To use Google Sheets instead of mock data:
1. Copy `.env.example` to `.env` and fill in your values
2. Set `USE_GOOGLE_SHEETS=true` in `.env`
3. Configure `GOOGLE_SHEETS_ID`, `GOOGLE_SHEET_TAB`, and `GOOGLE_SERVICE_ACCOUNT_FILE`

The app polls Google Sheets every 30 seconds (configurable via `POLL_INTERVAL_SECONDS` in `main.py`) and broadcasts updates to all connected clients.

## Key Business Rules

- Published schedule (`scheduled_start`/`scheduled_end`) is authoritative and never auto-modified
- Early finishes do NOT pull next act earlier - they extend break time
- Late finishes create slip that propagates downstream
- Slip formula: `projected_start[i] = scheduled_start[i] + slip`
- Conflict resolution: last-write-wins with timestamp
- Timezone: Festival local time only (PDT for Coachella)
- **Midnight rollover:** Acts past midnight (e.g. `01:00`) are stored as plain `time` objects; rollover is handled at comparison time. Server-side: `models.py` adds `timedelta(days=1)` when end < start. Client-side: `normalizeActTimes()` walks acts in sheet order and bumps any time that drops more than 1 hour below the previous act's time. Acts must be in chronological order in the sheet for this to work correctly.

## Client-Side Timer Architecture

The `updateTime()` method runs every second and is the single entry point for all per-tick logic. It queries `.act-row` elements once, parses their `data-*` attributes into a shared `acts` array, then passes `(currentSecs, acts)` to:
- `calculateSlip()` — computes accumulated slip from actual vs scheduled times
- `checkActAlerts()` — applies flash/warning CSS classes; suppresses `flash-warning` on act rows when the up-next section is already pulsing (act starting within 2 minutes) to avoid competing animations
- `updateNowPlaying()` — renders the now-playing/up-next banner; adds `starting-soon` pulse class when next act is ≤2 minutes away; updates countdown text in-place to avoid restarting CSS animations
- `updateCountdowns()` — shows `[Starts in X:XX]` for future acts, hidden once started or past scheduled time
- `updateOnDeckRows()` — adds `act-complete` to On Deck rows once local time passes their `scheduled_end`, hiding them via the same `hide-completed` mechanism as regular acts
- `updateLoadInRows()` — adds `act-complete` to Load In rows 1 hour after their `scheduled_start`

After WebSocket HTML swaps (from Google Sheets polling), `htmx:wsAfterMessage` triggers `updateTime()` to immediately re-apply countdowns and alerts before the browser paints. Use `htmx:wsAfterMessage` (not `htmx:afterSwap` or `htmx:afterSettle`) for flicker-free post-swap updates.

The time-of-day override (`timeOverride` / `frozenTime`) is only surfaced on `/preview`. It freezes `currentTime` to a fixed value so operators can inspect how the page renders at any point in the schedule without waiting for real time to advance. A `+24h` toggle adds 86400 seconds to `currentSecs` (without changing the displayed time string) to simulate post-midnight viewing.

## Offline Resilience

The app continues to function client-side if the server goes down after the page has loaded — Alpine.js keeps running the clock and all calculations using the last received schedule state. Two mechanisms protect against accidental data loss:

- **Server status indicator** — "Live Data" (green) / "Offline Data" (red) shown under the stage name, driven by `htmx:wsOpen` / `htmx:wsClose` events
- **`beforeunload` warning** — browser confirmation dialog fires if the user tries to close or refresh while offline
- **`overscroll-behavior: none`** — prevents pull-to-refresh on mobile

Note: a service worker cache was considered but removed — service workers require HTTPS, and this app runs over plain HTTP on LAN.

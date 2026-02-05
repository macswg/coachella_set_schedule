# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Festival Schedule Board - a real-time schedule tracking application for festival stages. Operators can view scheduled act times and record actual start/end times. The system tracks "slip" (accumulated lateness) and projects impacts on downstream acts.

Key domain concepts:
- **Slip**: Non-negative value representing how late the live timeline is vs published schedule
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
4. Alpine.js handles live clock and computed slip values client-side
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

Header row is expected at row 5, data starts at row 6. Rows without valid scheduled start/end times are skipped.

## MVP Scope

**Included:** Single stage, schedule display, actual time recording, slip tracking, WebSocket sync between operators

**Excluded:** Multi-stage support, artist photos, cloud hosting

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (auto-reload enabled)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Access the app
# Local: http://localhost:8000
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
│   └── components/
│       └── act_row.html # Single act row partial
└── static/
    └── styles.css       # Dark theme styles
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

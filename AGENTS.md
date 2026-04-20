# Repository Guidelines

## Project Structure & Module Organization

- `README.md`: one-line project summary.
- `PRD.md`: product requirements and domain rules (source of truth for “slip”, projections, and break behavior).
- `CLAUDE.md`: agent-focused overview of the intended architecture.
- `secret/`: reserved for local-only materials (keep empty in git; do not commit credentials).

Code layout:
- `main.py`: FastAPI app entry point, routes, background polling, WebSocket hub.
- `app/`: server-side modules:
  - `config.py`, `models.py`, `slip.py`, `websocket.py` — core logic (backend-agnostic)
  - `store.py` — in-memory mock backend (`DATA_BACKEND=memory`)
  - `sheets.py` — Google Sheets backend (`DATA_BACKEND=sheets`)
  - `sqlite_store.py` — SQLite backend (`DATA_BACKEND=sqlite`); same interface as `store.py`/`sheets.py`
  - `db/engine.py`, `db/models.py` — SQLAlchemy engine + ORM models (Show, Act, RecordingEvent, AppSetting); `init_db()` runs Alembic migrations on startup
  - `artnet.py`, `recorder.py`, `triggers.py`, `ntfy.py`, `notifier.py`, `companion.py` — optional integrations
- `alembic/` + `alembic.ini`: database migration tooling (versions: `0001_initial`, `0002_act_category`, `0003_app_settings`).
- `templates/`: Jinja2 templates:
  - `base.html` (shared head with CDN scripts + `schedule_utils.js`; renders show name label in header)
  - `index.html` (main schedule view + Alpine.js app)
  - `stage.html` (large-format stage display)
  - `history.html` / `history_detail.html` (slip/variance summary + per-act drill-down)
  - `admin/shows.html` / `admin/show_detail.html` (schedule editor, SQLite only)
  - `components/act_row.html` (per-act partial)
  - `components/app_nav.html` (unified top nav rendered on `/edit`, `/admin`, `/history`)
- `static/styles.css`: dark theme styles.
- `static/schedule_utils.js`: shared client-side helpers (`timeToSeconds`, `normalizeActTimes`, `formatCountdown`) loaded by `base.html` and used by both `index.html` and `stage.html`.

## Build, Test, and Development Commands

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
venv/bin/pip install -r requirements.txt

# Run development server (auto-reload enabled)
venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Access the app
# View-only: http://localhost:8000
# Operator:  http://localhost:8000/edit
```

## Coding Style & Naming Conventions

- Keep changes small and focused; avoid drive-by refactors.
- Prefer descriptive names matching the PRD vocabulary: `scheduled_start`, `actual_end`, `slip`, `projected_break`.
- Use consistent time units and document them (seconds vs milliseconds) at module boundaries.
- Client-side timers: all per-second logic runs through `updateTime()` which queries the DOM once and passes parsed data to sub-methods. Do not add separate `querySelectorAll('.act-row')` calls — use the shared `acts` array.
- For post-WebSocket-swap JS, use `htmx:wsAfterMessage` (not `afterSwap`/`afterSettle`) to avoid flicker.
- Formatting/linting tools are TBD; if you add one, wire it into CI and document how to run it locally.

## Testing Guidelines

- Add tests alongside new logic, especially around PRD acceptance criteria (early finish vs late finish behavior).
- Use deterministic time in tests (inject “now” rather than reading system time).
- Name tests by behavior (e.g., `test_early_finish_extends_break`).

## Commit & Pull Request Guidelines

- Commits in history are short and plain (e.g., `Initial commit`, `adds .gitignore and PRD.md`); follow the same style.
- PRs should include: what changed, why, and how to validate (commands or manual steps).
- For UI changes, include screenshots or a short screen recording.

## Security & Configuration Tips

- Never commit API keys, OAuth tokens, or Google service account files.
- If you add config, provide a checked-in example (e.g., `.env.example`) and keep real secrets in untracked files.

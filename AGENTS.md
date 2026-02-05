# Repository Guidelines

## Project Structure & Module Organization

- `README.md`: one-line project summary.
- `PRD.md`: product requirements and domain rules (source of truth for “slip”, projections, and break behavior).
- `CLAUDE.md`: agent-focused overview of the intended architecture.
- `secret/`: reserved for local-only materials (keep empty in git; do not commit credentials).

Planned code layout (once scaffolding lands):
- `frontend/`: web UI (single-stage schedule board).
- `backend/`: API + WebSocket sync service.
- `*/tests/`: tests colocated per layer.

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

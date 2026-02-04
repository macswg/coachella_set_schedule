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

This repo is currently documentation-first and does not yet include runnable app code. When you introduce scaffolding, also add the canonical commands to `README.md` and keep them consistent across environments (local + CI), e.g.:
- `frontend/`: `npm run dev`, `npm test`, `npm run lint`
- `backend/`: `python -m pytest`, `python -m ruff check`, `python -m uvicorn ...`

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

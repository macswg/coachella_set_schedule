# Phase 3 — Backend Selector + Config

**Issue:** [#33](https://github.com/macswg/coachella_set_schedule/issues/33)
**Epic:** [#30](https://github.com/macswg/coachella_set_schedule/issues/30)
**Depends on:** Phase 2
**Blocks:** Phase 4

## Context

Let each deployment pick its backend via `DATA_BACKEND`. Keep the existing `USE_GOOGLE_SHEETS` flag working as a deprecated shim.

## Files

- `app/config.py` — add `DATA_BACKEND` with validation.
- `main.py` — replace direct `store = ...` import with `store = _select_store()` based on config; log which backend was chosen.
- `.env.example` — add `DATA_BACKEND=sheets` with comments explaining the three options.
- `CLAUDE.md`, `README.md` — document the new var; mark `USE_GOOGLE_SHEETS` as deprecated.

## Acceptance criteria

- `DATA_BACKEND=sqlite`, `sheets`, `memory` all boot and serve `/edit` correctly.
- `USE_GOOGLE_SHEETS=true` alone (no `DATA_BACKEND`) still selects Sheets and logs a deprecation warning.
- Invalid value → server fails fast with a clear error.

## Verification

```bash
for backend in sheets sqlite memory; do
  DATA_BACKEND=$backend uvicorn main:app --port 8000 &
  sleep 2
  curl -fsS http://localhost:8000/ > /dev/null && echo "$backend ok"
  kill %1
done
```

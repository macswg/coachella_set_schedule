# Phase 2 — SQLite Store Backend

**Issue:** [#32](https://github.com/macswg/coachella_set_schedule/issues/32) — closed
**Epic:** [#30](https://github.com/macswg/coachella_set_schedule/issues/30)
**Status:** ✅ done in commit `f0cdf15`
**Depends on:** Phase 1
**Blocks:** Phase 3, 4

## Context

Implement `app/sqlite_store.py` so SQLite can serve the same read/write surface as `app/sheets.py` and `app/store.py`. Pydantic `Act` in `app/models.py` stays the boundary type: SQLAlchemy rows get converted at the store edge.

## Files

- `app/sqlite_store.py` (new) — implements:
  - `get_schedule() -> Schedule`
  - `update_actual_start(act_name, t)`, `update_actual_end(act_name, t)`
  - `start_screentime(act_name)`, `stop_screentime(act_name)`, `write_active_screentimes()`
  - `clear_actual_times(act_name)`
  - `advance_show()`, `reset_all()` (dev)
- `tests/test_sqlite_store.py` (new) — SQLite-specific: migration replay, persistence across session close.
- `tests/test_store.py` (edit) — parametrize existing tests over all three stores.

## Acceptance criteria

- `tests/test_store.py` green across `memory`, `sheets` (mocked), `sqlite`.
- `tests/test_sqlite_store.py` green: creating a session, writing an actual start, closing+reopening the engine, reading it back.
- END OF SHOW, load-in, on-deck semantics identical to existing stores.

## Verification

```bash
python -m pytest tests/test_store.py tests/test_sqlite_store.py -v
```

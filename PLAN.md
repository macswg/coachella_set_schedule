# PLAN: Internal Database Backend

Live index for the internal-DB feature. See `PRD.md#internal-database-backend` for the product spec. Each phase below links to a self-contained spec in `plans/` and a GitHub sub-issue of the epic.

**Epic:** [#30](https://github.com/macswg/coachella_set_schedule/issues/30)
**Branch:** `internal_database`
**Status:** Phase 1 in progress

## Phases

| # | Phase | Spec | Issue | Status |
|---|-------|------|-------|--------|
| 1 | Foundation & schema | [plans/phase-01-foundation.md](plans/phase-01-foundation.md) | [#31](https://github.com/macswg/coachella_set_schedule/issues/31) | in progress |
| 2 | SQLite store backend | [plans/phase-02-sqlite-store.md](plans/phase-02-sqlite-store.md) | [#32](https://github.com/macswg/coachella_set_schedule/issues/32) | pending |
| 3 | Backend selector + config | [plans/phase-03-backend-selector.md](plans/phase-03-backend-selector.md) | [#33](https://github.com/macswg/coachella_set_schedule/issues/33) | pending |
| 4 | Schedule editor UI | [plans/phase-04-editor-ui.md](plans/phase-04-editor-ui.md) | [#34](https://github.com/macswg/coachella_set_schedule/issues/34) | pending |
| 5 | Multi-show retention | [plans/phase-05-retention.md](plans/phase-05-retention.md) | [#35](https://github.com/macswg/coachella_set_schedule/issues/35) | pending |
| 6 | Export (JSON + CSV) | [plans/phase-06-export.md](plans/phase-06-export.md) | [#36](https://github.com/macswg/coachella_set_schedule/issues/36) | pending |
| 7 | Analytics (stretch) | [plans/phase-07-analytics.md](plans/phase-07-analytics.md) | [#37](https://github.com/macswg/coachella_set_schedule/issues/37) | pending |

## Cross-cutting invariants

- Pydantic `Act` in `app/models.py` remains the boundary type between store and app — do not leak SQLAlchemy rows upward.
- All three stores (`app/store.py`, `app/sheets.py`, new `app/sqlite_store.py`) must satisfy the same method signatures exercised by `tests/test_store.py`.
- The 30s poll loop in `main.py:36-53` stays unchanged; the DB store plugs in as a third backend.
- WebSocket broadcast path (`app/websocket.py`) unchanged.

## End-to-end acceptance (after Phase 4)

1. `DATA_BACKEND=sqlite` in `.env`, start server fresh.
2. `/admin` — create show "W1Shw1", add 5 acts with times.
3. `/edit` — operate show (mark start/stop/screentime).
4. Restart container — state persists; `/edit` renders mid-run state.
5. Switch to `DATA_BACKEND=sheets`, restart — Sheets path still works.
6. `python -m pytest` passes for all three stores.

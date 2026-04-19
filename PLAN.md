# PLAN: Internal Database Backend

Live index for the internal-DB feature. See `PRD.md#internal-database-backend` for the product spec. Each phase below links to a self-contained spec in `plans/` and a GitHub sub-issue of the epic.

**Epic:** [#30](https://github.com/macswg/coachella_set_schedule/issues/30)
**Branch:** `internal_database`
**Status:** Phases 1–5 complete. Phase 6 up next.

## Phases

| # | Phase | Spec | Issue | Status |
|---|-------|------|-------|--------|
| 1 | Foundation & schema | [plans/phase-01-foundation.md](plans/phase-01-foundation.md) | [#31](https://github.com/macswg/coachella_set_schedule/issues/31) | ✅ done (`f0cdf15`) |
| 2 | SQLite store backend | [plans/phase-02-sqlite-store.md](plans/phase-02-sqlite-store.md) | [#32](https://github.com/macswg/coachella_set_schedule/issues/32) | ✅ done (`f0cdf15`) |
| 3 | Backend selector + config | [plans/phase-03-backend-selector.md](plans/phase-03-backend-selector.md) | [#33](https://github.com/macswg/coachella_set_schedule/issues/33) | ✅ done (`f0cdf15`) |
| 4 | Schedule editor UI + category field | [plans/phase-04-editor-ui.md](plans/phase-04-editor-ui.md) | [#34](https://github.com/macswg/coachella_set_schedule/issues/34) | ✅ done (`3ae39fa`, `c5a1582`) |
| 5 | Multi-show retention | [plans/phase-05-retention.md](plans/phase-05-retention.md) | [#35](https://github.com/macswg/coachella_set_schedule/issues/35) | ✅ done |
| 6 | Export (JSON + CSV) | [plans/phase-06-export.md](plans/phase-06-export.md) | [#36](https://github.com/macswg/coachella_set_schedule/issues/36) | pending |
| 7 | Analytics (stretch) | [plans/phase-07-analytics.md](plans/phase-07-analytics.md) | [#37](https://github.com/macswg/coachella_set_schedule/issues/37) | pending |

## Scope adds landed after original plan

- **Explicit `category` field on `Act`** — added during Phase 4. Columns: `set`, `loadin`, `ondeck`, `changeover`, `preshow`, `end`. Replaces fragile name-based detection in `app/models.py` with a DB-backed authoritative value; name inference kept as fallback so the Google Sheets backend keeps working. Migration `0002_act_category` backfills existing rows.

## Cross-cutting invariants

- Pydantic `Act` in `app/models.py` remains the boundary type between store and app — do not leak SQLAlchemy rows upward.
- All three stores (`app/store.py`, `app/sheets.py`, `app/sqlite_store.py`) must satisfy the same method signatures exercised by `tests/test_store.py`.
- The 30s poll loop in `main.py:36-53` stays unchanged; the DB store plugs in as a third backend.
- WebSocket broadcast path (`app/websocket.py`) unchanged.
- `effective_category` on `Act` is the canonical accessor — don't branch on `act.category` directly.

## End-to-end acceptance (after Phase 4 — verified)

1. ✅ `DATA_BACKEND=sqlite` in `.env`, start server fresh.
2. ✅ `/admin` — create show, add acts with times and categories.
3. ✅ `/edit` — operate show (mark start/stop/screentime).
4. ✅ Restart container — state persists; `/edit` renders mid-run state.
5. ✅ Switch to `DATA_BACKEND=sheets`, restart — Sheets path still works.
6. ✅ `python -m pytest` passes: 212/212.

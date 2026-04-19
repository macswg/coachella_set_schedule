# Phase 7 — Analytics (stretch)

**Issue:** [#37](https://github.com/macswg/coachella_set_schedule/issues/37)
**Epic:** [#30](https://github.com/macswg/coachella_set_schedule/issues/30)
**Depends on:** Phase 5

## Context

Now that we retain per-show history, surface aggregate insights: per-show slip summary, per-act variance, completion rates. Server-computed on the SQLite store; no new persistence.

## Files

- `main.py` — `GET /history` route (gated by `EDIT_PASSWORD`).
- `templates/history.html` — list of shows with slip/variance summaries; drill-down per show.
- `app/slip.py` — extend with aggregation helpers (`summarize_show`, `per_act_variance`).
- `app/sqlite_store.py` — read helpers for archived shows with full act data.

## Acceptance criteria

- `/history` lists all retained + archived shows newest-first with max slip, avg variance, % acts started/completed.
- Drill-down shows each act's scheduled vs actual.
- Works with zero archived shows (empty-state message).

## Verification

Manual: run two shows end-to-end via `/edit`, advance between them, visit `/history`, verify numbers match intuition.

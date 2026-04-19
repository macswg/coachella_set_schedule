# Phase 4 — Schedule Editor UI

**Issue:** [#34](https://github.com/macswg/coachella_set_schedule/issues/34)
**Epic:** [#30](https://github.com/macswg/coachella_set_schedule/issues/30)
**Depends on:** Phase 3
**Blocks:** Phase 5 (clean dependency), Phase 6

## Context

Without Sheets, operators need an in-app way to create shows and edit the act list. Build `/admin` — HTMX + Alpine, dark theme matching the rest of the app, gated by `EDIT_PASSWORD`.

## Files

- `main.py` — new routes under `/admin`: show list, show detail, create/rename/delete show, CRUD acts.
- `templates/admin/shows.html`, `templates/admin/show_detail.html`, `templates/admin/_act_row.html`.
- `app/sqlite_store.py` — add admin helpers: `create_show`, `rename_show`, `delete_show`, `add_act`, `update_act`, `delete_act`, `reorder_acts`.
- `static/styles.css` — admin-specific styles (table rows, inline edit).

## Acceptance criteria

- Admin page requires `EDIT_PASSWORD`.
- Create a show, add acts with names + times, drag or arrow-button reorder, delete an act — all reflected in DB.
- After creation, `/edit` immediately renders the new show (current show = newly created, or explicit "set as current" button).
- Import: upload a JSON file matching the documented schema and it populates a show.
- Import from Sheets: given a configured `GOOGLE_SHEETS_ID`+tab, one-click pull creates a show in SQLite from Sheet contents.
- Write-through to Sheets is NOT attempted; `/admin` is a no-op when `DATA_BACKEND != sqlite` (render a friendly message).

## Verification

Manual smoke test end-to-end acceptance steps 1–3 in `PLAN.md`.

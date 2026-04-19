# Phase 6 — Export (JSON + CSV)

**Issue:** [#36](https://github.com/macswg/coachella_set_schedule/issues/36) — closed
**Epic:** [#30](https://github.com/macswg/coachella_set_schedule/issues/30)
**Status:** ✅ done
**Depends on:** Phase 5 (needs archive table to export older shows)

## Context

Operators keeping data externally need a clean export path. CSV output matches the existing Google Sheet column layout (C/D/E/F/G/H from `CLAUDE.md`) so it can be pasted back into Sheets if desired.

## Files

- `main.py` — `GET /admin/shows/{id}/export.json`, `GET /admin/shows/{id}/export.csv` (both live and archived shows).
- `app/sqlite_store.py` — `export_show_rows(show_id) -> list[dict]` helper.
- `templates/admin/show_detail.html` — export buttons.

## Acceptance criteria

- JSON export includes all `Act` fields and show metadata.
- CSV export: header row matches Sheet schema; body rows are insertable back into a Sheet without fixup.
- Archived shows exportable.
- Download filename: `{show_name}_{YYYY-MM-DD}.{ext}`.

## Verification

```bash
curl -u :$EDIT_PASSWORD -o test.csv http://localhost:8000/admin/shows/1/export.csv
head -1 test.csv   # matches documented Sheet column order
```

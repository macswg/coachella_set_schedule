# Phase 5 — Multi-show Retention

**Issue:** [#35](https://github.com/macswg/coachella_set_schedule/issues/35) — closed
**Epic:** [#30](https://github.com/macswg/coachella_set_schedule/issues/30)
**Status:** ✅ done
**Depends on:** Phase 4

## Context

Keep the live DB lean: `current` and `previous` shows are the hot rows; everything older moves to archive. Archived rows stay queryable for export (Phase 6) and analytics (Phase 7) but don't hit the default read path.

## Files

- `alembic/versions/0002_archive.py` — add `archived_shows` table (same columns as `shows`+ `acts` materialized, or a single `shows.is_archived` flag — decide in spec).
- `app/db/models.py` — reflect the new structure.
- `app/sqlite_store.py` — `advance_show()` demotes current → previous and moves old previous to archive; add `list_archived_shows()`, `restore_archived_show(id)`.
- `app/config.py` — `ARCHIVE_RETENTION_COUNT` (default 20), auto-purge oldest when exceeded.

## Acceptance criteria

- Advancing shows twice leaves exactly 2 live shows; older ones present but marked archived.
- `/edit` never renders archived shows.
- `ARCHIVE_RETENTION_COUNT=3` keeps archive capped at 3 oldest-purged-first.

## Verification

```bash
python -m pytest tests/test_sqlite_store.py -k retention -v
```

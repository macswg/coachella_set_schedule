"""
SQLite-backed store implementation.

Satisfies the same read/write interface as app/store.py and app/sheets.py so
it can drop into main.py via the DATA_BACKEND selector.

The Pydantic Act in app.models is the boundary type — SQLAlchemy rows are
converted at the store edge and never leak upward.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.engine import get_engine
from app.db.models import Act as ActRow, AppSetting, Show
from app.models import ACT_CATEGORIES, Act, infer_category, time_to_secs


# In-memory screentime session tracking (parallels the Sheets store pattern).
_screentime_sessions: dict[str, time] = {}


def _session() -> Session:
    from sqlalchemy.orm import sessionmaker
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)()


def _now_local() -> time:
    return datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()


def _elapsed_seconds(session_start: time, now: time) -> int:
    elapsed = time_to_secs(now) - time_to_secs(session_start)
    if elapsed < 0:
        elapsed += 86400
    return elapsed


def _current_show(session: Session) -> Optional[Show]:
    stmt = select(Show).where(Show.is_current.is_(True), Show.is_archived.is_(False))
    return session.scalars(stmt).first()


def _previous_show(session: Session) -> Optional[Show]:
    stmt = select(Show).where(Show.is_previous.is_(True), Show.is_archived.is_(False))
    return session.scalars(stmt).first()


def _enforce_archive_retention(session: Session) -> None:
    """Delete archived shows beyond ARCHIVE_RETENTION_COUNT, oldest first."""
    cap = settings.ARCHIVE_RETENTION_COUNT
    if cap <= 0:
        return
    stmt = (
        select(Show)
        .where(Show.is_archived.is_(True))
        .order_by(Show.position.asc(), Show.id.asc())
    )
    archived = list(session.scalars(stmt))
    overflow = len(archived) - cap
    for victim in archived[:max(0, overflow)]:
        session.delete(victim)


def _row_to_act(row: ActRow, *, running_session_start: Optional[time] = None) -> Act:
    return Act(
        act_name=row.act_name,
        scheduled_start=row.scheduled_start,
        scheduled_end=row.scheduled_end,
        actual_start=row.actual_start,
        actual_end=row.actual_end,
        screentime_total_seconds=row.screentime_total_seconds,
        screentime_session_start=running_session_start or row.screentime_session_start,
        category=row.category,
    )


def _act_rows_for_current_show(session: Session) -> list[ActRow]:
    show = _current_show(session)
    if show is None:
        return []
    return list(show.acts)


def _find_row(session: Session, act_name: str) -> Optional[ActRow]:
    show = _current_show(session)
    if show is None:
        return None
    for row in show.acts:
        if row.act_name == act_name:
            return row
    return None


# ----------------------------------------------------------------------------
# Read API
# ----------------------------------------------------------------------------

def get_schedule() -> list[Act]:
    """Fetch all acts for the current show.

    Handles END OF SHOW rows that lack a scheduled_start by inheriting the
    previous act's scheduled_end (matches the Sheets store semantics).
    """
    with _session() as session:
        rows = _act_rows_for_current_show(session)

    acts: list[Act] = []
    last_scheduled_end: Optional[time] = None
    for row in rows:
        scheduled_start = row.scheduled_start
        if (
            (row.act_name or "").lower().strip() in ("end", "end of show")
            and scheduled_start is None
            and last_scheduled_end is not None
        ):
            scheduled_start = last_scheduled_end

        if not row.act_name or scheduled_start is None:
            continue

        if row.scheduled_end is not None:
            last_scheduled_end = row.scheduled_end

        acts.append(
            Act(
                act_name=row.act_name,
                scheduled_start=scheduled_start,
                scheduled_end=row.scheduled_end,
                actual_start=row.actual_start,
                actual_end=row.actual_end,
                screentime_total_seconds=row.screentime_total_seconds,
                screentime_session_start=_screentime_sessions.get(row.act_name, row.screentime_session_start),
                category=row.category,
            )
        )
    return acts


def get_act(act_name: str) -> Optional[Act]:
    for act in get_schedule():
        if act.act_name == act_name:
            return act
    return None


# ----------------------------------------------------------------------------
# Write API
# ----------------------------------------------------------------------------

def update_actual_start(act_name: str, actual_time: time) -> Optional[Act]:
    with _session() as session:
        row = _find_row(session, act_name)
        if row is None:
            return None
        row.actual_start = actual_time
        session.commit()
    return get_act(act_name)


def update_actual_end(act_name: str, actual_time: time) -> Optional[Act]:
    with _session() as session:
        row = _find_row(session, act_name)
        if row is None:
            return None
        row.actual_end = actual_time
        session.commit()
    return get_act(act_name)


def clear_actual_times(act_name: str) -> Optional[Act]:
    with _session() as session:
        row = _find_row(session, act_name)
        if row is None:
            return None
        row.actual_start = None
        row.actual_end = None
        row.screentime_total_seconds = 0
        row.screentime_session_start = None
        session.commit()
    _screentime_sessions.pop(act_name, None)
    return get_act(act_name)


def start_screentime(act_name: str) -> Optional[Act]:
    session_start = _now_local()
    _screentime_sessions[act_name] = session_start
    with _session() as session:
        row = _find_row(session, act_name)
        if row is None:
            return None
        row.screentime_session_start = session_start
        session.commit()
    return get_act(act_name)


def stop_screentime(act_name: str) -> Optional[Act]:
    if act_name not in _screentime_sessions:
        return get_act(act_name)

    session_start = _screentime_sessions.pop(act_name)
    elapsed = _elapsed_seconds(session_start, _now_local())

    with _session() as session:
        row = _find_row(session, act_name)
        if row is None:
            return None
        row.screentime_total_seconds = (row.screentime_total_seconds or 0) + elapsed
        row.screentime_session_start = None
        session.commit()
    return get_act(act_name)


def write_active_screentimes() -> None:
    """Persist in-flight screentime totals so progress survives a restart.

    Same cadence as the Sheets store's periodic flush.
    """
    if not _screentime_sessions:
        return
    now = _now_local()
    with _session() as session:
        show = _current_show(session)
        if show is None:
            return
        for row in show.acts:
            session_start = _screentime_sessions.get(row.act_name)
            if session_start is None:
                continue
            elapsed = _elapsed_seconds(session_start, now)
            # Persist an up-to-date running total: last committed total stays in
            # screentime_total_seconds, and the live delta is recoverable via
            # screentime_session_start timestamp.
            row.screentime_session_start = session_start
        session.commit()


# ----------------------------------------------------------------------------
# Show metadata
# ----------------------------------------------------------------------------

def get_stage_name() -> str:
    return settings.STAGE_NAME


def get_current_show() -> str:
    with _session() as session:
        show = _current_show(session)
        return show.name if show else ""


def _next_show(session: Session) -> Optional[Show]:
    current = _current_show(session)
    if current is None:
        return None
    stmt = (
        select(Show)
        .where(
            Show.position > current.position,
            Show.is_archived.is_(False),
        )
        .order_by(Show.position.asc())
    )
    return session.scalars(stmt).first()


def has_next_show() -> bool:
    with _session() as session:
        return _next_show(session) is not None


def get_next_show() -> str:
    with _session() as session:
        nxt = _next_show(session)
        return nxt.name if nxt else ""


def advance_show() -> str:
    """Demote current to previous, archive the old previous, promote next to current.

    Retention policy: keep exactly one `current` and one `previous` live.
    Everything else stays in the archive (oldest purged beyond
    ARCHIVE_RETENTION_COUNT). Clears in-memory screentime session tracking.
    """
    global _screentime_sessions
    with _session() as session:
        current = _current_show(session)
        nxt = _next_show(session)
        if nxt is None:
            raise ValueError("Already on the last show")

        # Archive any existing previous show
        for prev in session.scalars(select(Show).where(Show.is_previous.is_(True))):
            prev.is_previous = False
            prev.is_archived = True

        if current is not None:
            current.is_current = False
            current.is_previous = True

        nxt.is_current = True
        nxt.is_previous = False
        nxt.is_archived = False

        _enforce_archive_retention(session)
        session.commit()
        new_name = nxt.name

    _screentime_sessions = {}
    return new_name


def archive_show(show_id: int) -> None:
    """Explicitly archive a show (for manual cleanup)."""
    with _session() as session:
        show = session.get(Show, show_id)
        if show is None:
            raise ValueError(f"Show id={show_id} not found")
        show.is_current = False
        show.is_previous = False
        show.is_archived = True
        _enforce_archive_retention(session)
        session.commit()


def restore_show(show_id: int) -> None:
    """Un-archive a show without promoting it to current."""
    with _session() as session:
        show = session.get(Show, show_id)
        if show is None:
            raise ValueError(f"Show id={show_id} not found")
        show.is_archived = False
        session.commit()


# ----------------------------------------------------------------------------
# Admin helpers (used by Phase 4 editor UI; minimal surface now for testing)
# ----------------------------------------------------------------------------

def create_show(name: str, *, make_current: bool = False) -> Show:
    with _session() as session:
        existing = session.scalars(select(Show).where(Show.name == name)).first()
        if existing is not None:
            raise ValueError(f"Show {name!r} already exists")
        max_pos = session.scalars(select(Show).order_by(Show.position.desc())).first()
        position = (max_pos.position + 1) if max_pos else 0
        if make_current:
            for other in session.scalars(select(Show).where(Show.is_current.is_(True))):
                other.is_current = False
                other.is_previous = True
        show = Show(name=name, position=position, is_current=make_current)
        session.add(show)
        session.commit()
        session.refresh(show)
        return show


def add_act(
    show_name: str,
    *,
    act_name: str,
    scheduled_start: Optional[time],
    scheduled_end: Optional[time] = None,
    row_index: Optional[int] = None,
    category: Optional[str] = None,
) -> ActRow:
    with _session() as session:
        show = session.scalars(select(Show).where(Show.name == show_name)).first()
        if show is None:
            raise ValueError(f"Show {show_name!r} not found")
        if row_index is None:
            row_index = (max((a.row_index for a in show.acts), default=-1)) + 1
        resolved_category = category if category in ACT_CATEGORIES else infer_category(act_name)
        row = ActRow(
            show_id=show.id,
            row_index=row_index,
            act_name=act_name,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
            category=resolved_category,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def reset_screentime_sessions() -> None:
    """Test helper — clear in-memory screentime session tracking."""
    global _screentime_sessions
    _screentime_sessions = {}


# ----------------------------------------------------------------------------
# App settings (key/value runtime config editable from /admin)
# ----------------------------------------------------------------------------

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with _session() as session:
        row = session.get(AppSetting, key)
        return row.value if row is not None else default


def set_setting(key: str, value: Optional[str]) -> None:
    with _session() as session:
        row = session.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key, value=value)
            session.add(row)
        else:
            row.value = value
        session.commit()


# ----------------------------------------------------------------------------
# Admin CRUD (used by Phase 4 /admin UI)
# ----------------------------------------------------------------------------

def list_shows() -> list[dict]:
    """Return all shows (including archived) with metadata for the admin UI."""
    with _session() as session:
        stmt = select(Show).order_by(Show.position.asc(), Show.id.asc())
        out: list[dict] = []
        for show in session.scalars(stmt):
            out.append({
                "id": show.id,
                "name": show.name,
                "position": show.position,
                "is_current": show.is_current,
                "is_previous": show.is_previous,
                "is_archived": show.is_archived,
                "act_count": len(show.acts),
            })
        return out


def get_show_detail(show_id: int) -> Optional[dict]:
    with _session() as session:
        show = session.get(Show, show_id)
        if show is None:
            return None
        return {
            "id": show.id,
            "name": show.name,
            "is_current": show.is_current,
            "is_previous": show.is_previous,
            "is_archived": show.is_archived,
            "acts": [
                {
                    "id": a.id,
                    "row_index": a.row_index,
                    "act_name": a.act_name,
                    "scheduled_start": a.scheduled_start,
                    "scheduled_end": a.scheduled_end,
                    "actual_start": a.actual_start,
                    "actual_end": a.actual_end,
                    "screentime_total_seconds": a.screentime_total_seconds,
                    "category": a.category or infer_category(a.act_name),
                }
                for a in show.acts
            ],
        }


def rename_show(show_id: int, new_name: str) -> None:
    with _session() as session:
        show = session.get(Show, show_id)
        if show is None:
            raise ValueError(f"Show id={show_id} not found")
        show.name = new_name
        session.commit()


def delete_show(show_id: int) -> None:
    with _session() as session:
        show = session.get(Show, show_id)
        if show is None:
            return
        session.delete(show)
        session.commit()


def set_current_show(show_id: int) -> None:
    with _session() as session:
        target = session.get(Show, show_id)
        if target is None:
            raise ValueError(f"Show id={show_id} not found")
        for other in session.scalars(select(Show).where(Show.is_current.is_(True))):
            other.is_current = False
            other.is_previous = True
        target.is_current = True
        target.is_previous = False
        target.is_archived = False
        session.commit()


def update_act(
    act_id: int,
    *,
    act_name: Optional[str] = None,
    scheduled_start: Optional[time] = None,
    scheduled_end: Optional[time] = None,
    clear_end: bool = False,
    category: Optional[str] = None,
) -> None:
    with _session() as session:
        row = session.get(ActRow, act_id)
        if row is None:
            raise ValueError(f"Act id={act_id} not found")
        if act_name is not None:
            row.act_name = act_name
        if scheduled_start is not None:
            row.scheduled_start = scheduled_start
        if clear_end:
            row.scheduled_end = None
        elif scheduled_end is not None:
            row.scheduled_end = scheduled_end
        if category is not None and category in ACT_CATEGORIES:
            row.category = category
        session.commit()


def delete_act(act_id: int) -> None:
    with _session() as session:
        row = session.get(ActRow, act_id)
        if row is None:
            return
        session.delete(row)
        session.commit()


def move_act(act_id: int, direction: str) -> None:
    """Swap row_index with the adjacent act in the same show. direction = 'up' | 'down'."""
    if direction not in ("up", "down"):
        raise ValueError("direction must be 'up' or 'down'")
    with _session() as session:
        row = session.get(ActRow, act_id)
        if row is None:
            raise ValueError(f"Act id={act_id} not found")

        siblings = sorted(row.show.acts, key=lambda a: a.row_index)
        idx = next(i for i, a in enumerate(siblings) if a.id == row.id)
        neighbor_idx = idx - 1 if direction == "up" else idx + 1
        if neighbor_idx < 0 or neighbor_idx >= len(siblings):
            return
        neighbor = siblings[neighbor_idx]
        original = row.row_index
        target = neighbor.row_index
        # Three-step swap to satisfy UNIQUE(show_id, row_index): park row at
        # a sentinel, move neighbor, then place row at the vacated slot.
        row.row_index = -1
        session.flush()
        neighbor.row_index = original
        session.flush()
        row.row_index = target
        session.commit()


def export_show(show_id: int) -> Optional[dict]:
    """Return a serializable export payload for a show (live or archived)."""
    with _session() as session:
        show = session.get(Show, show_id)
        if show is None:
            return None

        def _fmt_time(t: Optional[time]) -> Optional[str]:
            return t.strftime("%H:%M:%S") if t else None

        return {
            "name": show.name,
            "is_archived": show.is_archived,
            "is_current": show.is_current,
            "is_previous": show.is_previous,
            "acts": [
                {
                    "row_index": a.row_index,
                    "act_name": a.act_name,
                    "category": a.category or infer_category(a.act_name),
                    "scheduled_start": _fmt_time(a.scheduled_start),
                    "scheduled_end": _fmt_time(a.scheduled_end),
                    "actual_start": _fmt_time(a.actual_start),
                    "actual_end": _fmt_time(a.actual_end),
                    "screentime_total_seconds": a.screentime_total_seconds,
                }
                for a in show.acts
            ],
        }


def import_show_from_json(payload: dict) -> int:
    """Import a show from a JSON payload. Returns the new show id.

    Expected shape:
        {"name": "W1Shw1", "make_current": true,
         "acts": [{"act_name": "...", "scheduled_start": "HH:MM", "scheduled_end": "HH:MM"}, ...]}
    """
    name = payload.get("name")
    if not name:
        raise ValueError("Import payload missing 'name'")
    make_current = bool(payload.get("make_current", False))
    show = create_show(name, make_current=make_current)

    def _parse(value: Optional[str]) -> Optional[time]:
        if not value:
            return None
        for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
        raise ValueError(f"Unparseable time: {value!r}")

    for entry in payload.get("acts", []):
        add_act(
            show.name,
            act_name=entry["act_name"],
            scheduled_start=_parse(entry.get("scheduled_start")),
            scheduled_end=_parse(entry.get("scheduled_end")),
            category=entry.get("category"),
        )
    return show.id

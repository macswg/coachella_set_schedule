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
from app.db.models import Act as ActRow, Show
from app.models import Act, time_to_secs


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


def _row_to_act(row: ActRow, *, running_session_start: Optional[time] = None) -> Act:
    return Act(
        act_name=row.act_name,
        scheduled_start=row.scheduled_start,
        scheduled_end=row.scheduled_end,
        actual_start=row.actual_start,
        actual_end=row.actual_end,
        screentime_total_seconds=row.screentime_total_seconds,
        screentime_session_start=running_session_start or row.screentime_session_start,
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
    """Demote current to previous (if any), promote next to current.

    Clears in-memory screentime session tracking.
    """
    global _screentime_sessions
    with _session() as session:
        current = _current_show(session)
        nxt = _next_show(session)
        if nxt is None:
            raise ValueError("Already on the last show")

        # Clear any prior is_previous
        for prev in session.scalars(select(Show).where(Show.is_previous.is_(True))):
            prev.is_previous = False

        if current is not None:
            current.is_current = False
            current.is_previous = True

        nxt.is_current = True
        nxt.is_previous = False
        session.commit()
        new_name = nxt.name

    _screentime_sessions = {}
    return new_name


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
) -> ActRow:
    with _session() as session:
        show = session.scalars(select(Show).where(Show.name == show_name)).first()
        if show is None:
            raise ValueError(f"Show {show_name!r} not found")
        if row_index is None:
            row_index = (max((a.row_index for a in show.acts), default=-1)) + 1
        row = ActRow(
            show_id=show.id,
            row_index=row_index,
            act_name=act_name,
            scheduled_start=scheduled_start,
            scheduled_end=scheduled_end,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row


def reset_screentime_sessions() -> None:
    """Test helper — clear in-memory screentime session tracking."""
    global _screentime_sessions
    _screentime_sessions = {}

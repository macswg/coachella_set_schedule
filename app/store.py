from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.config import settings
from typing import Optional
from app.models import Act


# In-memory mock data store for development
_schedule: list[Act] = [
    Act(
        act_name="Load In - Main Stage",
        scheduled_start=time(10, 0),
    ),
    Act(
        act_name="On Deck - Sunrise Collective",
        scheduled_start=time(11, 0),
    ),
    Act(
        act_name="Sunrise Collective",
        scheduled_start=time(11, 30),
        scheduled_end=time(12, 0),
    ),
    Act(
        act_name="Desert Echoes",
        scheduled_start=time(12, 0),
        scheduled_end=time(13, 45),
    ),
    Act(
        act_name="Neon Mirage",
        scheduled_start=time(14, 0),
        scheduled_end=time(14, 45),
    ),
    Act(
        act_name="Cosmic Wanderers",
        scheduled_start=time(15, 15),
        scheduled_end=time(16, 15),
    ),
    Act(
        act_name="Valley Vibes",
        scheduled_start=time(16, 30),
        scheduled_end=time(17, 30),
    ),
    Act(
        act_name="Mojave Dreams",
        scheduled_start=time(18, 0),
        scheduled_end=time(19, 15),
    ),
    Act(
        act_name="Indio Nights",
        scheduled_start=time(19, 45),
        scheduled_end=time(21, 0),
    ),
    Act(
        act_name="The Headliners",
        scheduled_start=time(21, 30),
        scheduled_end=time(23, 30),
    ),
]

# In-memory screentime session tracking (survives schedule list rebuilds)
_screentime_sessions: dict[str, time] = {}


def _find_act_index(act_name: str) -> Optional[int]:
    """Return the index of an act in _schedule, or None if not found."""
    for i, act in enumerate(_schedule):
        if act.act_name == act_name:
            return i
    return None


def _elapsed_seconds(session_start: time, now: time) -> int:
    """Compute elapsed seconds between two times, handling midnight crossing."""
    start_secs = session_start.hour * 3600 + session_start.minute * 60 + session_start.second
    now_secs = now.hour * 3600 + now.minute * 60 + now.second
    elapsed = now_secs - start_secs
    if elapsed < 0:
        elapsed += 86400
    return elapsed


def get_schedule() -> list[Act]:
    """Get the current schedule."""
    return _schedule.copy()


def get_act(act_name: str) -> Optional[Act]:
    """Get a single act by name."""
    i = _find_act_index(act_name)
    return _schedule[i] if i is not None else None


def update_actual_start(act_name: str, actual_time: time) -> Optional[Act]:
    """Update the actual start time for an act."""
    i = _find_act_index(act_name)
    if i is None:
        return None
    _schedule[i] = _schedule[i].model_copy(update={"actual_start": actual_time})
    return _schedule[i]


def update_actual_end(act_name: str, actual_time: time) -> Optional[Act]:
    """Update the actual end time for an act."""
    i = _find_act_index(act_name)
    if i is None:
        return None
    _schedule[i] = _schedule[i].model_copy(update={"actual_end": actual_time})
    return _schedule[i]


def clear_actual_times(act_name: str) -> Optional[Act]:
    """Clear both actual start and end times for an act."""
    i = _find_act_index(act_name)
    if i is None:
        return None
    _schedule[i] = _schedule[i].model_copy(update={
        "actual_start": None,
        "actual_end": None,
        "screentime_total_seconds": 0,
        "screentime_session_start": None,
    })
    _screentime_sessions.pop(act_name, None)
    return _schedule[i]


def start_screentime(act_name: str) -> Optional[Act]:
    """Start a screentime session for an act."""
    session_start = datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()
    _screentime_sessions[act_name] = session_start
    i = _find_act_index(act_name)
    if i is None:
        return None
    _schedule[i] = _schedule[i].model_copy(update={"screentime_session_start": session_start})
    return _schedule[i]


def stop_screentime(act_name: str) -> Optional[Act]:
    """Stop a screentime session and accumulate total for an act."""
    if act_name not in _screentime_sessions:
        return get_act(act_name)

    session_start = _screentime_sessions.pop(act_name)
    now = datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()
    elapsed = _elapsed_seconds(session_start, now)

    i = _find_act_index(act_name)
    if i is None:
        return None
    new_total = _schedule[i].screentime_total_seconds + elapsed
    _schedule[i] = _schedule[i].model_copy(update={
        "screentime_total_seconds": new_total,
        "screentime_session_start": None,
    })
    return _schedule[i]


def write_active_screentimes() -> None:
    """No-op for in-memory store — sessions are already in memory."""
    pass


def get_stage_name() -> str:
    """Get the stage name."""
    return settings.STAGE_NAME


def get_current_show() -> str:
    """No multi-show support in mock store."""
    return ""


def has_next_show() -> bool:
    """No multi-show support in mock store."""
    return False


def get_next_show() -> str:
    """No multi-show support in mock store."""
    return ""

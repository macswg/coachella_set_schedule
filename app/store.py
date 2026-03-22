from datetime import datetime, time
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

STAGE_NAME = "Main Stage"

# In-memory screentime session tracking (survives schedule list rebuilds)
_screentime_sessions: dict[str, time] = {}


def get_schedule() -> list[Act]:
    """Get the current schedule."""
    return _schedule.copy()


def get_act(act_name: str) -> Optional[Act]:
    """Get a single act by name."""
    for act in _schedule:
        if act.act_name == act_name:
            return act
    return None


def update_actual_start(act_name: str, actual_time: time) -> Optional[Act]:
    """Update the actual start time for an act."""
    for i, act in enumerate(_schedule):
        if act.act_name == act_name:
            _schedule[i] = act.model_copy(update={"actual_start": actual_time})
            return _schedule[i]
    return None


def update_actual_end(act_name: str, actual_time: time) -> Optional[Act]:
    """Update the actual end time for an act."""
    for i, act in enumerate(_schedule):
        if act.act_name == act_name:
            _schedule[i] = act.model_copy(update={"actual_end": actual_time})
            return _schedule[i]
    return None


def clear_actual_times(act_name: str) -> Optional[Act]:
    """Clear both actual start and end times for an act."""
    for i, act in enumerate(_schedule):
        if act.act_name == act_name:
            _schedule[i] = act.model_copy(update={
                "actual_start": None,
                "actual_end": None,
                "screentime_total_seconds": 0,
                "screentime_session_start": None,
            })
            _screentime_sessions.pop(act_name, None)
            return _schedule[i]
    return None


def start_screentime(act_name: str) -> Optional[Act]:
    """Start a screentime session for an act."""
    session_start = datetime.now().time()
    _screentime_sessions[act_name] = session_start
    for i, act in enumerate(_schedule):
        if act.act_name == act_name:
            _schedule[i] = act.model_copy(update={"screentime_session_start": session_start})
            return _schedule[i]
    return None


def stop_screentime(act_name: str) -> Optional[Act]:
    """Stop a screentime session and accumulate total for an act."""
    if act_name not in _screentime_sessions:
        return get_act(act_name)

    session_start = _screentime_sessions.pop(act_name)
    now = datetime.now().time()

    # Compute elapsed seconds, handle midnight crossing
    start_secs = session_start.hour * 3600 + session_start.minute * 60 + session_start.second
    now_secs = now.hour * 3600 + now.minute * 60 + now.second
    elapsed = now_secs - start_secs
    if elapsed < 0:
        elapsed += 86400

    for i, act in enumerate(_schedule):
        if act.act_name == act_name:
            new_total = act.screentime_total_seconds + elapsed
            _schedule[i] = act.model_copy(update={
                "screentime_total_seconds": new_total,
                "screentime_session_start": None,
            })
            return _schedule[i]
    return None


def get_stage_name() -> str:
    """Get the stage name."""
    return STAGE_NAME

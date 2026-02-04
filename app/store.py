from datetime import time
from typing import Optional
from app.models import Act


# In-memory mock data store for development
_schedule: list[Act] = [
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
        scheduled_end=time(15, 0),
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
            })
            return _schedule[i]
    return None


def get_stage_name() -> str:
    """Get the stage name."""
    return STAGE_NAME

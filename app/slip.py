from datetime import datetime, time, timedelta
from typing import Optional
from app.models import Act


def time_to_datetime(t: time) -> datetime:
    """Convert a time to a datetime on today's date."""
    return datetime.combine(datetime.today(), t)


def datetime_to_time(dt: datetime) -> time:
    """Convert a datetime to a time."""
    return dt.time()


def add_seconds_to_time(t: time, seconds: int) -> time:
    """Add seconds to a time value."""
    dt = time_to_datetime(t)
    result = dt + timedelta(seconds=seconds)
    return result.time()


def calculate_slip(acts: list[Act], current_time: Optional[time] = None) -> int:
    """
    Calculate current slip in seconds (always >= 0).

    Slip is the accumulated lateness in the schedule. It's determined by:
    - For completed acts: how late the act ended vs scheduled
    - For in-progress acts: projected end based on scheduled duration

    Early finishes do NOT create negative slip - they just extend breaks.
    """
    if current_time is None:
        current_time = datetime.now().time()

    slip = 0

    for act in acts:
        if act.actual_end:
            # Act completed - check if it ran late
            end_variance = act.end_variance or 0
            slip = max(0, end_variance)
        elif act.actual_start and not act.actual_end:
            # Act in progress - project when it will end
            actual_start_dt = time_to_datetime(act.actual_start)
            projected_end_dt = actual_start_dt + timedelta(seconds=act.scheduled_duration)
            scheduled_end_dt = time_to_datetime(act.scheduled_end)

            # Slip is how late the projected end is vs scheduled
            projected_slip = int((projected_end_dt - scheduled_end_dt).total_seconds())
            slip = max(0, projected_slip)

    return slip


def project_times(acts: list[Act], slip: int) -> list[dict]:
    """
    Project start/end times for all acts based on current slip.

    Returns a list of dicts with:
    - act_name: str
    - projected_start: time
    - projected_end: time
    - status: 'complete' | 'in_progress' | 'pending'
    """
    projections = []

    for act in acts:
        if act.is_complete():
            # Completed acts use their actual times
            projections.append({
                "act_name": act.act_name,
                "projected_start": act.actual_start,
                "projected_end": act.actual_end,
                "status": "complete",
            })
        elif act.is_in_progress():
            # In-progress acts: use actual start, project end
            actual_start_dt = time_to_datetime(act.actual_start)
            projected_end_dt = actual_start_dt + timedelta(seconds=act.scheduled_duration)
            projections.append({
                "act_name": act.act_name,
                "projected_start": act.actual_start,
                "projected_end": projected_end_dt.time(),
                "status": "in_progress",
            })
        else:
            # Pending acts: apply slip but never pull earlier than scheduled
            projected_start = add_seconds_to_time(act.scheduled_start, slip)
            projected_end = add_seconds_to_time(act.scheduled_end, slip)
            projections.append({
                "act_name": act.act_name,
                "projected_start": projected_start,
                "projected_end": projected_end,
                "status": "pending",
            })

    return projections


def calculate_break_remaining(
    current_act: Act,
    next_act: Act,
    slip: int,
    current_time: Optional[time] = None
) -> Optional[int]:
    """
    Calculate remaining break time between acts in seconds.

    Returns None if current act hasn't ended yet.
    Returns negative value if break is being eaten into (running late).
    """
    if current_time is None:
        current_time = datetime.now().time()

    if not current_act.actual_end:
        return None

    # Break ends when next act is projected to start
    next_projected_start = add_seconds_to_time(next_act.scheduled_start, slip)
    next_start_dt = time_to_datetime(next_projected_start)
    current_dt = time_to_datetime(current_time)

    return int((next_start_dt - current_dt).total_seconds())


def format_duration(seconds: int) -> str:
    """Format a duration in seconds to a human-readable string."""
    if seconds < 0:
        return f"-{format_duration(abs(seconds))}"

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return f"{secs}s"


def format_variance(seconds: Optional[int]) -> str:
    """Format a variance value with +/- prefix."""
    if seconds is None:
        return ""
    if seconds == 0:
        return "on time"
    elif seconds > 0:
        return f"+{format_duration(seconds)}"
    else:
        return format_duration(seconds)

from datetime import datetime, time, timedelta
from typing import Optional

from app.models import Act


def time_to_datetime(t: time) -> datetime:
    """Convert a time to a datetime on today's date."""
    return datetime.combine(datetime.today(), t)


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
        if act.is_loadin or act.is_ondeck or act.is_end_of_show or act.is_preshow:
            continue
        if act.actual_end:
            # Act completed - check if it ran late
            end_variance = act.end_variance or 0
            slip = max(0, end_variance)
        elif act.actual_start and not act.actual_end:
            # Act in progress - project when it will end
            if act.scheduled_end is None:
                continue
            actual_start_dt = time_to_datetime(act.actual_start)
            projected_end_dt = actual_start_dt + timedelta(seconds=act.scheduled_duration)
            scheduled_end_dt = time_to_datetime(act.scheduled_end)
            if scheduled_end_dt < actual_start_dt:
                scheduled_end_dt += timedelta(days=1)

            # Slip is how late the projected end is vs scheduled
            projected_slip = int((projected_end_dt - scheduled_end_dt).total_seconds())
            slip = max(0, projected_slip)

    return slip


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

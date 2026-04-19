from datetime import datetime, time, timedelta
from typing import Iterable, Optional

from app.models import Act, infer_category


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


def summarize_show(show_payload: dict) -> dict:
    """Aggregate stats for a show export payload (from sqlite_store.export_show).

    Returns: {act_count, set_count, started_count, completed_count,
              max_start_variance_seconds, max_end_variance_seconds,
              avg_start_variance_seconds, avg_end_variance_seconds}
    Variances are computed only for acts that recorded times; means skip Nones.
    """
    def _parse(value):
        if not value:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
        return None

    def _signed_variance(scheduled, actual):
        if scheduled is None or actual is None:
            return None
        scheduled_dt = datetime.combine(datetime.today(), scheduled)
        actual_dt = datetime.combine(datetime.today(), actual)
        if actual_dt < scheduled_dt - timedelta(hours=12):
            actual_dt += timedelta(days=1)
        return int((actual_dt - scheduled_dt).total_seconds())

    act_count = 0
    set_count = 0
    started = 0
    completed = 0
    start_variances: list[int] = []
    end_variances: list[int] = []
    for a in show_payload.get("acts", []):
        category = (a.get("category") or infer_category(a.get("act_name", ""))).lower()
        act_count += 1
        is_set = category == "set"
        if is_set:
            set_count += 1
        sched_s = _parse(a.get("scheduled_start"))
        sched_e = _parse(a.get("scheduled_end"))
        act_s = _parse(a.get("actual_start"))
        act_e = _parse(a.get("actual_end"))
        if act_s is not None:
            started += 1
        if act_s is not None and act_e is not None:
            completed += 1
        sv = _signed_variance(sched_s, act_s)
        ev = _signed_variance(sched_e, act_e)
        if sv is not None:
            start_variances.append(sv)
        if ev is not None:
            end_variances.append(ev)

    def _avg(values: list[int]) -> Optional[int]:
        return int(sum(values) / len(values)) if values else None

    def _max(values: list[int]) -> Optional[int]:
        return max(values) if values else None

    denom = set_count if set_count else act_count
    return {
        "name": show_payload.get("name"),
        "act_count": act_count,
        "set_count": set_count,
        "started_count": started,
        "completed_count": completed,
        "pct_started": round(100 * started / denom, 1) if denom else 0.0,
        "pct_completed": round(100 * completed / denom, 1) if denom else 0.0,
        "max_start_variance_seconds": _max(start_variances),
        "max_end_variance_seconds": _max(end_variances),
        "avg_start_variance_seconds": _avg(start_variances),
        "avg_end_variance_seconds": _avg(end_variances),
        "is_current": show_payload.get("is_current", False),
        "is_archived": show_payload.get("is_archived", False),
    }

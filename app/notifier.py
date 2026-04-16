"""
Schedule-based ntfy push notifications.

Fires notifications for:
- 5 minutes before a scheduled act start
- 10 minutes before a scheduled act end
- Act started (actual start recorded)
- Act ended (actual end recorded)

Called from the poll loop (time-based) and from API endpoints (action-based).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.models import Act, time_to_secs

# Tracks which acts have already sent each notification type this session.
# Server restart re-arms all notifications — intentional.
_notified_starting: set[str] = set()
_notified_ending: set[str] = set()

# Notification fires when now is within this window around the target time.
# Should be >= poll interval (30s) to avoid missing the window.
_WINDOW_SECONDS = 45


def _in_window(now_secs: int, target_secs: int) -> bool:
    """True if now is within _WINDOW_SECONDS before target, handling midnight wrap."""
    diff = (target_secs - now_secs) % 86400
    return 0 <= diff <= _WINDOW_SECONDS


def check_and_notify(acts: list[Act]) -> None:
    """
    Check schedule and fire time-based notifications.
    Call once per poll cycle.
    """
    from app.ntfy import notify

    if not settings.NTFY_URL:
        return

    now = datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()
    now_secs = time_to_secs(now)

    for act in acts:
        if act.is_loadin or act.is_ondeck or act.is_changeover or act.is_preshow:
            continue

        name = act.act_name

        # 5 minutes before scheduled start
        if act.actual_start is None and name not in _notified_starting:
            target = (time_to_secs(act.scheduled_start) - 300) % 86400
            if _in_window(now_secs, target):
                notify(
                    title=f"Starting in ~5 min: {name}",
                    message=f"{name} is scheduled to start at {act.scheduled_start.strftime('%H:%M')}",
                    priority="high",
                    tags=["bell"],
                )
                _notified_starting.add(name)

        # 10 minutes before scheduled end (only if act has started)
        if act.actual_start is not None and act.actual_end is None and name not in _notified_ending:
            target = (time_to_secs(act.scheduled_end) - 600) % 86400
            if _in_window(now_secs, target):
                notify(
                    title=f"Ending in ~10 min: {name}",
                    message=f"{name} is scheduled to end at {act.scheduled_end.strftime('%H:%M')}",
                    priority="high",
                    tags=["stopwatch"],
                )
                _notified_ending.add(name)


def notify_act_started(act_name: str, time_str: str) -> None:
    """Call when an operator marks a set as started."""
    from app.ntfy import notify

    if not settings.NTFY_URL:
        return

    notify(
        title=f"Set started: {act_name}",
        message=f"{act_name} went on at {time_str}",
        priority="default",
        tags=["arrow_forward"],
    )


def notify_act_ended(act_name: str, time_str: str) -> None:
    """Call when an operator marks a set as complete."""
    from app.ntfy import notify

    if not settings.NTFY_URL:
        return

    notify(
        title=f"Set complete: {act_name}",
        message=f"{act_name} finished at {time_str}",
        priority="default",
        tags=["checkered_flag"],
    )

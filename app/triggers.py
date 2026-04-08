"""
Schedule-based trigger engine.

Checks the schedule each poll cycle and calls recorder.start_recording()
when an act is within RECORDING_PRE_START_MINUTES of its scheduled start.

State is in-memory: a server restart will re-arm all triggers. This is
intentional — if the server restarts mid-show, recording starts again
rather than being silently skipped.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.models import Act


# Runtime enable/disable toggle — starts from config, operators can flip it live
_enabled: bool = settings.RECORDING_ENABLED

# Acts triggered this session — prevents double-firing across poll cycles
_triggered: set[str] = set()

# How long after scheduled start to keep the trigger window open.
# Prevents late-night now_secs from matching early-morning trigger_secs.
_TRIGGER_GRACE_SECONDS = 3600

# Acts with active stop reminders shown on /edit
# Populated when triggered, cleared by operator via stop or dismiss
_active_reminders: set[str] = set()


def is_enabled() -> bool:
    return _enabled


def set_enabled(value: bool) -> None:
    global _enabled
    _enabled = value


def _time_to_secs(t) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


def check_and_fire(acts: list[Act]) -> list[str]:
    """
    Fire start_recording() for any acts newly entering their trigger window.
    Returns list of act names that were triggered this call.
    """
    from app import recorder

    now = datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()
    now_secs = _time_to_secs(now)
    pre_secs = settings.RECORDING_PRE_START_MINUTES * 60
    newly_triggered = []

    for act in acts:
        if act.is_loadin or act.is_ondeck or act.is_changeover or act.is_complete():
            continue
        if settings.RECORDING_ACT_PREFIX and not act.act_name.startswith(settings.RECORDING_ACT_PREFIX):
            continue
        if act.act_name in _triggered:
            continue

        start_secs = _time_to_secs(act.scheduled_start)
        trigger_secs = start_secs - pre_secs
        window_end = (start_secs + _TRIGGER_GRACE_SECONDS) % 86400

        if trigger_secs < 0:
            trigger_secs += 86400

        # Only fire within [trigger_secs, start + grace], handling midnight wrap.
        # Without the upper bound, a post-midnight act's tiny trigger_secs would
        # match any late-evening now_secs (e.g. 23:00 >= 00:25 in raw seconds).
        if trigger_secs <= window_end:
            in_window = trigger_secs <= now_secs <= window_end
        else:
            # Window crosses midnight (e.g. trigger at 23:55, window_end at 01:30)
            in_window = now_secs >= trigger_secs or now_secs <= window_end

        if in_window:
            try:
                recorder.start_recording(act.act_name)
            except Exception as e:
                print(f"[triggers] start_recording failed for {act.act_name!r}: {e}")
            _triggered.add(act.act_name)
            _active_reminders.add(act.act_name)
            newly_triggered.append(act.act_name)
            print(f"[triggers] triggered recording for {act.act_name!r}")

    return newly_triggered


def stop_and_dismiss(act_name: str) -> None:
    """Operator clicked Stop Recording. Calls stop_recording() and clears the reminder."""
    from app import recorder
    try:
        recorder.stop_recording(act_name)
    except Exception as e:
        print(f"[triggers] stop_recording failed for {act_name!r}: {e}")
    _active_reminders.discard(act_name)


def dismiss(act_name: str) -> None:
    """Dismiss the reminder without stopping recording (operator handled it another way)."""
    _active_reminders.discard(act_name)


def get_active_reminders() -> list[str]:
    """Return act names with active stop reminders."""
    return list(_active_reminders)


def clear_completed(acts: list[Act]) -> bool:
    """Auto-dismiss reminders for acts that have an actual_end recorded. Returns True if any changed."""
    changed = False
    for act in acts:
        if act.actual_end and act.act_name in _active_reminders:
            _active_reminders.discard(act.act_name)
            changed = True
    return changed

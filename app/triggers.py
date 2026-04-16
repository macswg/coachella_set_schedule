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
from app.models import Act, time_to_secs


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


def _normalize_act_start_secs(acts: list[Act]) -> dict[str, int]:
    """Walk acts in schedule order, bumping post-midnight start times past 86400.

    Mirrors client-side normalizeActTimes() logic so trigger windows are always
    evaluated in show-order time rather than raw clock time.  A show that runs
    from 22:00 to 02:00 produces normalized seconds like 79200, 82800, 86400,
    90000 instead of 79200, 82800, 0, 3600, which lets simple range comparisons
    work without any modulo gymnastics.
    """
    result: dict[str, int] = {}
    prev_secs = 0
    for act in acts:
        if act.is_loadin:
            result[act.act_name] = time_to_secs(act.scheduled_start)
            continue
        secs = time_to_secs(act.scheduled_start)
        if prev_secs > 0 and secs < prev_secs - 3600:
            secs += 86400
        result[act.act_name] = secs
        prev_secs = secs
    return result


def check_and_fire(acts: list[Act]) -> list[str]:
    """
    Fire start_recording() for any acts newly entering their trigger window.
    Returns list of act names that were triggered this call.
    """
    from app import recorder

    now = datetime.now(tz=ZoneInfo(settings.TIMEZONE)).time()
    now_secs = time_to_secs(now)
    pre_secs = settings.RECORDING_PRE_START_MINUTES * 60
    newly_triggered = []

    # Normalize act start times so post-midnight acts have secs > 86400.
    # This eliminates the need for modulo-based midnight-crossing logic.
    normalized = _normalize_act_start_secs(acts)
    max_start = max(normalized.values(), default=0)
    # If the show extends past midnight and we're currently in the early-morning
    # window (before 6am), treat now as next-day time too.
    if max_start >= 86400 and now_secs < 18000:  # treat as same show until 5am
        now_secs += 86400

    for act in acts:
        if act.is_loadin or act.is_ondeck or act.is_changeover or act.is_complete() or act.is_end_of_show or act.is_preshow:
            continue
        if settings.RECORDING_ACT_PREFIX and not act.act_name.startswith(settings.RECORDING_ACT_PREFIX):
            continue
        if act.act_name in _triggered:
            continue

        start_secs = normalized.get(act.act_name, time_to_secs(act.scheduled_start))
        trigger_secs = start_secs - pre_secs
        window_end = start_secs + _TRIGGER_GRACE_SECONDS

        if trigger_secs <= now_secs <= window_end:
            try:
                recorder.start_recording(act.act_name)
                _triggered.add(act.act_name)
                _active_reminders.add(act.act_name)
                newly_triggered.append(act.act_name)
                print(f"[triggers] triggered recording for {act.act_name!r}")
            except Exception as e:
                print(f"[triggers] start_recording failed for {act.act_name!r}: {e} — will retry next cycle")

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

"""
Tests for midnight rollover behaviour across a full schedule.

Scenarios: a festival day running from noon into the early hours of the next morning.
Acts in sheet order: 12:00, 14:00, 23:00, 01:00, 02:30
"""

from datetime import time
from app.models import Act
from app.slip import calculate_slip


def make_act(name, sched_start, sched_end, actual_start=None, actual_end=None):
    return Act(
        act_name=name,
        scheduled_start=sched_start,
        scheduled_end=sched_end,
        actual_start=actual_start,
        actual_end=actual_end,
    )


# ---------------------------------------------------------------------------
# Model: scheduled_duration across midnight
# ---------------------------------------------------------------------------

def test_duration_same_day():
    act = make_act("A", time(14, 0), time(15, 30))
    assert act.scheduled_duration == 90 * 60


def test_duration_crosses_midnight():
    act = make_act("A", time(23, 30), time(1, 0))
    assert act.scheduled_duration == 90 * 60


def test_duration_exactly_at_midnight_boundary():
    act = make_act("A", time(23, 0), time(0, 0))
    assert act.scheduled_duration == 3600


# ---------------------------------------------------------------------------
# Model: start_variance across midnight
# ---------------------------------------------------------------------------

def test_start_variance_late_crosses_midnight():
    # Scheduled 23:55, actually started 00:05 — 10 min late
    act = make_act("A", time(23, 55), time(1, 0), actual_start=time(0, 5))
    assert act.start_variance == 10 * 60


def test_start_variance_early_crosses_midnight():
    # Scheduled 00:10, actually started 00:05 — 5 min early
    act = make_act("A", time(0, 10), time(1, 0), actual_start=time(0, 5))
    assert act.start_variance == -5 * 60


# ---------------------------------------------------------------------------
# Model: end_variance across midnight
# ---------------------------------------------------------------------------

def test_end_variance_late_crosses_midnight():
    act = make_act("A", time(23, 0), time(1, 0), actual_start=time(23, 0), actual_end=time(1, 15))
    assert act.end_variance == 15 * 60


def test_end_variance_early_crosses_midnight():
    act = make_act("A", time(23, 0), time(1, 0), actual_start=time(23, 0), actual_end=time(0, 45))
    assert act.end_variance == -15 * 60


# ---------------------------------------------------------------------------
# Slip: multi-act schedule spanning midnight
# ---------------------------------------------------------------------------

def test_slip_propagates_across_midnight():
    """Late end before midnight should show as slip for next act after midnight."""
    acts = [
        make_act("Late Night", time(23, 0), time(0, 30),
                 actual_start=time(23, 0), actual_end=time(0, 40)),  # 10 min late
        make_act("After Midnight", time(0, 30), time(2, 0)),
    ]
    assert calculate_slip(acts) == 10 * 60


def test_slip_zero_when_on_time_across_midnight():
    acts = [
        make_act("Late Night", time(23, 0), time(0, 30),
                 actual_start=time(23, 0), actual_end=time(0, 30)),
        make_act("After Midnight", time(0, 30), time(2, 0)),
    ]
    assert calculate_slip(acts) == 0


def test_slip_in_progress_after_midnight():
    """Act that started 5 min late after midnight propagates correct slip."""
    acts = [
        make_act("Late Night", time(23, 0), time(0, 30),
                 actual_start=time(23, 0), actual_end=time(0, 30)),
        make_act("After Midnight", time(0, 30), time(2, 0),
                 actual_start=time(0, 35)),  # 5 min late start
    ]
    assert calculate_slip(acts) == 5 * 60


# ---------------------------------------------------------------------------
# Model: actual_duration across midnight
# ---------------------------------------------------------------------------

def test_actual_duration_crosses_midnight():
    act = make_act("A", time(23, 0), time(1, 0), actual_start=time(23, 0), actual_end=time(1, 0))
    assert act.actual_duration == 2 * 3600


def test_actual_duration_ran_long_crosses_midnight():
    act = make_act("A", time(23, 0), time(1, 0), actual_start=time(23, 0), actual_end=time(1, 15))
    assert act.actual_duration == 2 * 3600 + 15 * 60

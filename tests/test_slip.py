from datetime import time
from app.models import Act
from app.slip import calculate_slip, format_duration, format_variance


def make_act(sched_start, sched_end, actual_start=None, actual_end=None):
    return Act(
        act_name="Test",
        scheduled_start=sched_start,
        scheduled_end=sched_end,
        actual_start=actual_start,
        actual_end=actual_end,
    )


# --- calculate_slip ---

def test_slip_empty_list():
    assert calculate_slip([]) == 0


def test_slip_no_acts_started():
    acts = [make_act(time(12, 0), time(13, 0))]
    assert calculate_slip(acts) == 0


def test_slip_completed_on_time():
    acts = [
        make_act(time(12, 0), time(13, 0), actual_start=time(12, 0), actual_end=time(13, 0))
    ]
    assert calculate_slip(acts) == 0


def test_slip_completed_early_is_zero():
    # Early finishes never create negative slip
    acts = [
        make_act(time(12, 0), time(13, 0), actual_start=time(12, 0), actual_end=time(12, 50))
    ]
    assert calculate_slip(acts) == 0


def test_slip_completed_late():
    acts = [
        make_act(time(12, 0), time(13, 0), actual_start=time(12, 0), actual_end=time(13, 10))
    ]
    assert calculate_slip(acts) == 10 * 60


def test_slip_in_progress_on_time():
    # Started on time → projected end = scheduled end → no slip
    acts = [make_act(time(12, 0), time(13, 0), actual_start=time(12, 0))]
    assert calculate_slip(acts) == 0


def test_slip_in_progress_late_start():
    # Started 10 minutes late → projected end is 10 minutes late
    acts = [make_act(time(12, 0), time(13, 0), actual_start=time(12, 10))]
    assert calculate_slip(acts) == 10 * 60


# --- format_duration ---

def test_format_duration_zero():
    assert format_duration(0) == "0s"


def test_format_duration_seconds():
    assert format_duration(45) == "45s"


def test_format_duration_exactly_one_minute():
    assert format_duration(60) == "1m"


def test_format_duration_minutes():
    # 2m 30s → shows just minutes
    assert format_duration(150) == "2m"


def test_format_duration_exactly_one_hour():
    assert format_duration(3600) == "1h 0m"


def test_format_duration_hours_and_minutes():
    assert format_duration(3660) == "1h 1m"


def test_format_duration_negative():
    assert format_duration(-60) == "-1m"


# --- format_variance ---

def test_format_variance_none():
    assert format_variance(None) == ""


def test_format_variance_zero():
    assert format_variance(0) == "on time"


def test_format_variance_positive():
    assert format_variance(600) == "+10m"


def test_format_variance_negative():
    assert format_variance(-600) == "-10m"

from datetime import time
from app.models import Act


def make_act(**kwargs):
    defaults = dict(
        act_name="Test Act",
        scheduled_start=time(12, 0),
        scheduled_end=time(13, 0),
    )
    defaults.update(kwargs)
    return Act(**defaults)


# --- is_pending ---

def test_is_pending_no_start():
    act = make_act()
    assert act.is_pending() is True


def test_is_pending_with_start():
    act = make_act(actual_start=time(12, 0))
    assert act.is_pending() is False


# --- is_in_progress ---

def test_is_in_progress():
    act = make_act(actual_start=time(12, 0))
    assert act.is_in_progress() is True


def test_is_in_progress_not_started():
    act = make_act()
    assert act.is_in_progress() is False


def test_is_in_progress_completed():
    act = make_act(actual_start=time(12, 0), actual_end=time(13, 0))
    assert act.is_in_progress() is False


# --- is_complete ---

def test_is_complete():
    act = make_act(actual_start=time(12, 0), actual_end=time(13, 0))
    assert act.is_complete() is True


def test_is_complete_not_started():
    act = make_act()
    assert act.is_complete() is False


def test_is_complete_in_progress():
    act = make_act(actual_start=time(12, 0))
    assert act.is_complete() is False


# --- scheduled_duration ---

def test_scheduled_duration_one_hour():
    act = make_act(scheduled_start=time(12, 0), scheduled_end=time(13, 0))
    assert act.scheduled_duration == 3600


def test_scheduled_duration_partial_hour():
    act = make_act(scheduled_start=time(12, 0), scheduled_end=time(12, 45))
    assert act.scheduled_duration == 45 * 60


# --- actual_duration ---

def test_actual_duration_not_started():
    act = make_act()
    assert act.actual_duration is None


def test_actual_duration_in_progress():
    act = make_act(actual_start=time(12, 0))
    assert act.actual_duration is None


def test_actual_duration_complete():
    act = make_act(actual_start=time(12, 0), actual_end=time(13, 0))
    assert act.actual_duration == 3600


# --- start_variance ---

def test_start_variance_not_started():
    act = make_act()
    assert act.start_variance is None


def test_start_variance_on_time():
    act = make_act(actual_start=time(12, 0))
    assert act.start_variance == 0


def test_start_variance_late():
    act = make_act(actual_start=time(12, 5))  # 5 minutes late
    assert act.start_variance == 5 * 60


def test_start_variance_early():
    act = make_act(actual_start=time(11, 55))  # 5 minutes early
    assert act.start_variance == -5 * 60


# --- end_variance ---

def test_end_variance_not_ended():
    act = make_act()
    assert act.end_variance is None


def test_end_variance_on_time():
    act = make_act(actual_start=time(12, 0), actual_end=time(13, 0))
    assert act.end_variance == 0


def test_end_variance_late():
    act = make_act(actual_start=time(12, 0), actual_end=time(13, 10))
    assert act.end_variance == 10 * 60


def test_end_variance_early():
    act = make_act(actual_start=time(12, 0), actual_end=time(12, 50))
    assert act.end_variance == -10 * 60

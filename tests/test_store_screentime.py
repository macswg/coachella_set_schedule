import time as time_module
from datetime import time
from unittest.mock import patch
from app import store


ONDECK_ACT = "On Deck - Sunrise Collective"
REGULAR_ACT = "Sunrise Collective"


def _clear_all():
    for act in store.get_schedule():
        store.clear_actual_times(act.act_name)


def setup_function():
    _clear_all()


def teardown_function():
    _clear_all()


# --- start_screentime ---

def test_start_screentime_returns_act():
    result = store.start_screentime(ONDECK_ACT)
    assert result is not None
    assert result.act_name == ONDECK_ACT


def test_start_screentime_sets_session_start():
    fixed_time = time(14, 30, 0)
    with patch("app.store.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = fixed_time
        result = store.start_screentime(ONDECK_ACT)
    assert result.screentime_session_start == fixed_time


def test_start_screentime_unknown_act_returns_none():
    result = store.start_screentime("Unknown Act")
    assert result is None


def test_start_screentime_persists():
    store.start_screentime(ONDECK_ACT)
    acts = store.get_schedule()
    act = next(a for a in acts if a.act_name == ONDECK_ACT)
    assert act.screentime_session_start is not None


# --- stop_screentime ---

def test_stop_screentime_returns_act():
    store.start_screentime(ONDECK_ACT)
    result = store.stop_screentime(ONDECK_ACT)
    assert result is not None
    assert result.act_name == ONDECK_ACT


def test_stop_screentime_clears_session():
    store.start_screentime(ONDECK_ACT)
    result = store.stop_screentime(ONDECK_ACT)
    assert result.screentime_session_start is None


def test_stop_screentime_accumulates_total():
    start = time(14, 0, 0)
    stop = time(14, 0, 30)  # 30 seconds later

    with patch("app.store.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = start
        store.start_screentime(ONDECK_ACT)

    with patch("app.store.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = stop
        result = store.stop_screentime(ONDECK_ACT)

    assert result.screentime_total_seconds == 30


def test_stop_screentime_accumulates_across_sessions():
    start1, stop1 = time(14, 0, 0), time(14, 0, 20)
    start2, stop2 = time(14, 1, 0), time(14, 1, 10)

    with patch("app.store.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = start1
        store.start_screentime(ONDECK_ACT)
    with patch("app.store.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = stop1
        store.stop_screentime(ONDECK_ACT)

    with patch("app.store.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = start2
        store.start_screentime(ONDECK_ACT)
    with patch("app.store.datetime") as mock_dt:
        mock_dt.now.return_value.time.return_value = stop2
        result = store.stop_screentime(ONDECK_ACT)

    assert result.screentime_total_seconds == 30  # 20 + 10


def test_stop_screentime_without_start_returns_act():
    # Stopping without a running session should return the act unchanged
    result = store.stop_screentime(ONDECK_ACT)
    assert result is not None
    assert result.screentime_total_seconds == 0


def test_clear_resets_screentime():
    store.start_screentime(ONDECK_ACT)
    store.stop_screentime(ONDECK_ACT)
    result = store.clear_actual_times(ONDECK_ACT)
    assert result.screentime_total_seconds == 0
    assert result.screentime_session_start is None


def test_clear_stops_active_session():
    store.start_screentime(ONDECK_ACT)
    store.clear_actual_times(ONDECK_ACT)
    acts = store.get_schedule()
    act = next(a for a in acts if a.act_name == ONDECK_ACT)
    assert act.screentime_session_start is None

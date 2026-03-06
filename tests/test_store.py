import pytest
from datetime import time
from app import store

FIRST_ACT = "Sunrise Collective"
SECOND_ACT = "Desert Echoes"


def _clear_all():
    for act in store.get_schedule():
        store.clear_actual_times(act.act_name)


@pytest.fixture(autouse=True)
def reset_store():
    _clear_all()
    yield
    _clear_all()


# --- get_schedule ---

def test_get_schedule_returns_list():
    result = store.get_schedule()
    assert isinstance(result, list)
    assert len(result) > 0


def test_get_schedule_returns_copy():
    s1 = store.get_schedule()
    s2 = store.get_schedule()
    assert s1 is not s2


def test_get_schedule_copy_does_not_affect_store():
    copy = store.get_schedule()
    copy.clear()
    assert len(store.get_schedule()) > 0


# --- update_actual_start ---

def test_update_actual_start_returns_act():
    t = time(12, 5)
    result = store.update_actual_start(FIRST_ACT, t)
    assert result is not None
    assert result.actual_start == t


def test_update_actual_start_unknown_returns_none():
    result = store.update_actual_start("Unknown Act", time(12, 0))
    assert result is None


def test_update_actual_start_persists():
    t = time(12, 5)
    store.update_actual_start(FIRST_ACT, t)
    acts = store.get_schedule()
    act = next(a for a in acts if a.act_name == FIRST_ACT)
    assert act.actual_start == t


# --- update_actual_end ---

def test_update_actual_end_returns_act():
    t = time(13, 0)
    result = store.update_actual_end(FIRST_ACT, t)
    assert result is not None
    assert result.actual_end == t


def test_update_actual_end_unknown_returns_none():
    result = store.update_actual_end("Unknown Act", time(13, 0))
    assert result is None


def test_update_actual_end_persists():
    t = time(13, 5)
    store.update_actual_end(FIRST_ACT, t)
    acts = store.get_schedule()
    act = next(a for a in acts if a.act_name == FIRST_ACT)
    assert act.actual_end == t


# --- clear_actual_times ---

def test_clear_actual_times_resets_both():
    store.update_actual_start(FIRST_ACT, time(12, 5))
    store.update_actual_end(FIRST_ACT, time(13, 5))
    result = store.clear_actual_times(FIRST_ACT)
    assert result is not None
    assert result.actual_start is None
    assert result.actual_end is None


def test_clear_actual_times_unknown_returns_none():
    result = store.clear_actual_times("Unknown Act")
    assert result is None


def test_clear_actual_times_persists():
    store.update_actual_start(FIRST_ACT, time(12, 5))
    store.clear_actual_times(FIRST_ACT)
    acts = store.get_schedule()
    act = next(a for a in acts if a.act_name == FIRST_ACT)
    assert act.actual_start is None

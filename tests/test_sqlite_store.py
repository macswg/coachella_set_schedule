"""Tests for the SQLite-backed store (app/sqlite_store.py)."""

from __future__ import annotations

import importlib
from datetime import time
from pathlib import Path

import pytest


FIRST_ACT = "Sunrise Collective"
SECOND_ACT = "Desert Echoes"
END_OF_SHOW = "END OF SHOW"


def _reload_with_sqlite(tmp_path: Path):
    """Point config at a fresh SQLite file and reset engine singletons.

    Does NOT reload models/base — that would re-register tables on the same
    declarative metadata and raise InvalidRequestError.
    """
    from app.config import settings
    from app.db import engine as engine_module
    from app.db import models as db_models  # noqa: F401 — ensure models registered
    from app import sqlite_store

    settings.SQLITE_PATH = str(tmp_path / "schedule.db")
    engine_module._engine = None
    engine_module._SessionLocal = None
    engine_module.init_db()
    sqlite_store.reset_screentime_sessions()
    return sqlite_store


def _seed(store, *, show_name: str = "W1Shw1") -> None:
    store.create_show(show_name, make_current=True)
    store.add_act(show_name, act_name="Load In - Main", scheduled_start=time(10, 0))
    store.add_act(show_name, act_name="On Deck - Sunrise Collective", scheduled_start=time(11, 0))
    store.add_act(show_name, act_name=FIRST_ACT, scheduled_start=time(11, 30), scheduled_end=time(12, 0))
    store.add_act(show_name, act_name=SECOND_ACT, scheduled_start=time(12, 0), scheduled_end=time(13, 45))
    store.add_act(show_name, act_name="The Headliners", scheduled_start=time(21, 30), scheduled_end=time(23, 30))
    store.add_act(show_name, act_name=END_OF_SHOW, scheduled_start=None)


@pytest.fixture
def store(tmp_path):
    s = _reload_with_sqlite(tmp_path)
    _seed(s)
    yield s


# --- get_schedule ---

def test_schedule_returns_seeded_acts(store):
    acts = store.get_schedule()
    names = [a.act_name for a in acts]
    assert FIRST_ACT in names
    assert SECOND_ACT in names


def test_schedule_end_of_show_inherits_previous_end(store):
    acts = store.get_schedule()
    eos = next(a for a in acts if a.is_end_of_show)
    # Previous act is The Headliners ending at 23:30
    assert eos.scheduled_start == time(23, 30)


# --- actual time CRUD ---

def test_update_actual_start_persists(store):
    t = time(11, 32)
    result = store.update_actual_start(FIRST_ACT, t)
    assert result is not None and result.actual_start == t
    assert store.get_act(FIRST_ACT).actual_start == t


def test_update_actual_start_unknown_returns_none(store):
    assert store.update_actual_start("Does Not Exist", time(12, 0)) is None


def test_update_actual_end_persists(store):
    t = time(12, 5)
    store.update_actual_end(FIRST_ACT, t)
    assert store.get_act(FIRST_ACT).actual_end == t


def test_clear_actual_times_resets_both(store):
    store.update_actual_start(FIRST_ACT, time(11, 32))
    store.update_actual_end(FIRST_ACT, time(12, 5))
    cleared = store.clear_actual_times(FIRST_ACT)
    assert cleared.actual_start is None and cleared.actual_end is None


# --- screentime ---

def test_screentime_start_stop_accumulates(store, monkeypatch):
    # Freeze "now" so elapsed is deterministic
    t0 = time(11, 0, 0)
    t1 = time(11, 0, 10)
    calls = iter([t0, t1])
    monkeypatch.setattr(store, "_now_local", lambda: next(calls))

    store.start_screentime("On Deck - Sunrise Collective")
    stopped = store.stop_screentime("On Deck - Sunrise Collective")
    assert stopped.screentime_total_seconds == 10
    assert stopped.screentime_session_start is None


def test_screentime_stop_without_start_noop(store):
    result = store.stop_screentime("On Deck - Sunrise Collective")
    assert result is not None
    assert result.screentime_total_seconds == 0


# --- persistence across reopen ---

def test_state_persists_across_engine_reopen(tmp_path):
    store = _reload_with_sqlite(tmp_path)
    _seed(store)
    store.update_actual_start(FIRST_ACT, time(11, 33))

    # Drop engine caches to simulate process restart against the same DB file
    from app.db import engine as engine_module
    engine_module._engine = None
    engine_module._SessionLocal = None

    act = store.get_act(FIRST_ACT)
    assert act is not None and act.actual_start == time(11, 33)


# --- multi-show ---

def test_advance_show(store):
    assert store.get_current_show() == "W1Shw1"
    assert store.has_next_show() is False

    store.create_show("W1Shw2", make_current=False)
    store.add_act("W1Shw2", act_name="Opener", scheduled_start=time(10, 0), scheduled_end=time(10, 30))

    assert store.has_next_show() is True
    assert store.get_next_show() == "W1Shw2"

    new_name = store.advance_show()
    assert new_name == "W1Shw2"
    assert store.get_current_show() == "W1Shw2"
    # Previously current show is now flagged previous
    acts = store.get_schedule()
    assert [a.act_name for a in acts] == ["Opener"]


def test_advance_show_without_next_raises(store):
    with pytest.raises(ValueError):
        store.advance_show()

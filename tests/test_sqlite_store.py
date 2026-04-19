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


# --- admin helpers (Phase 4) ---

def test_list_shows_reports_act_counts(store):
    shows = store.list_shows()
    w1 = next(s for s in shows if s["name"] == "W1Shw1")
    assert w1["is_current"] is True
    assert w1["act_count"] == 6


def test_set_current_show_swaps_flags(store):
    store.create_show("W1Shw2", make_current=False)
    w2 = next(s for s in store.list_shows() if s["name"] == "W1Shw2")
    store.set_current_show(w2["id"])
    shows = {s["name"]: s for s in store.list_shows()}
    assert shows["W1Shw2"]["is_current"] is True
    assert shows["W1Shw1"]["is_current"] is False
    assert shows["W1Shw1"]["is_previous"] is True


def test_update_act_changes_fields(store):
    detail = store.get_show_detail(1)
    first_act_id = detail["acts"][0]["id"]
    store.update_act(first_act_id, act_name="Renamed", scheduled_start=time(9, 0))
    detail = store.get_show_detail(1)
    row = next(a for a in detail["acts"] if a["id"] == first_act_id)
    assert row["act_name"] == "Renamed"
    assert row["scheduled_start"] == time(9, 0)


def test_move_act_swaps_with_neighbor(store):
    detail = store.get_show_detail(1)
    ordered_before = [a["act_name"] for a in detail["acts"]]
    second_id = detail["acts"][1]["id"]
    store.move_act(second_id, "up")
    detail = store.get_show_detail(1)
    ordered_after = [a["act_name"] for a in detail["acts"]]
    assert ordered_after[0] == ordered_before[1]
    assert ordered_after[1] == ordered_before[0]


def test_delete_act_removes_row(store):
    detail = store.get_show_detail(1)
    victim_id = detail["acts"][0]["id"]
    store.delete_act(victim_id)
    detail = store.get_show_detail(1)
    assert all(a["id"] != victim_id for a in detail["acts"])


# --- retention (Phase 5) ---

def test_advance_show_archives_old_previous(store):
    store.create_show("W1Shw2", make_current=False)
    store.add_act("W1Shw2", act_name="Opener", scheduled_start=time(10, 0))
    store.advance_show()
    shows = {s["name"]: s for s in store.list_shows()}
    assert shows["W1Shw2"]["is_current"] is True
    assert shows["W1Shw1"]["is_previous"] is True
    assert shows["W1Shw1"]["is_archived"] is False

    store.create_show("W1Shw3", make_current=False)
    store.add_act("W1Shw3", act_name="Closer", scheduled_start=time(20, 0))
    store.advance_show()
    shows = {s["name"]: s for s in store.list_shows()}
    assert shows["W1Shw3"]["is_current"] is True
    assert shows["W1Shw2"]["is_previous"] is True
    assert shows["W1Shw1"]["is_archived"] is True  # the old previous got archived


def test_archive_retention_purges_beyond_cap(store, monkeypatch):
    # Force a tiny archive cap
    from app.config import settings as app_settings
    monkeypatch.setattr(app_settings, "ARCHIVE_RETENTION_COUNT", 1)

    # Seed 4 future shows; advance 3 times. Old previous gets archived each
    # advance, but only the most-recent archived survives the cap-1 purge.
    for idx in range(2, 6):
        store.create_show(f"W1Shw{idx}", make_current=False)
        store.add_act(f"W1Shw{idx}", act_name="Placeholder", scheduled_start=time(12, 0))
    store.advance_show()
    store.advance_show()
    store.advance_show()

    archived = [s for s in store.list_shows() if s["is_archived"]]
    assert len(archived) == 1


def test_archive_and_restore(store):
    store.create_show("W1Shw2", make_current=False)
    w2 = next(s for s in store.list_shows() if s["name"] == "W1Shw2")
    store.archive_show(w2["id"])
    assert next(s for s in store.list_shows() if s["id"] == w2["id"])["is_archived"] is True
    store.restore_show(w2["id"])
    assert next(s for s in store.list_shows() if s["id"] == w2["id"])["is_archived"] is False


def test_export_show_round_trip(store):
    payload = store.export_show(1)
    assert payload is not None
    assert payload["name"] == "W1Shw1"
    names = [a["act_name"] for a in payload["acts"]]
    assert FIRST_ACT in names
    # scheduled times are serialized as strings
    sunrise = next(a for a in payload["acts"] if a["act_name"] == FIRST_ACT)
    assert sunrise["scheduled_start"] == "11:30:00"
    assert sunrise["scheduled_end"] == "12:00:00"


def test_export_show_missing_returns_none(store):
    assert store.export_show(9999) is None


def test_import_show_from_json(store):
    payload = {
        "name": "Imported",
        "make_current": False,
        "acts": [
            {"act_name": "Act A", "scheduled_start": "10:00"},
            {"act_name": "Act B", "scheduled_start": "11:00", "scheduled_end": "11:30"},
        ],
    }
    show_id = store.import_show_from_json(payload)
    detail = store.get_show_detail(show_id)
    assert detail["name"] == "Imported"
    assert [a["act_name"] for a in detail["acts"]] == ["Act A", "Act B"]
    assert detail["acts"][1]["scheduled_end"] == time(11, 30)

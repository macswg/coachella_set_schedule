"""
Tests for _screentime_totals in-memory cache in sheets.py.

The cache exists to prevent stale Google Sheets reads immediately after a write.
After stop_screentime() writes a new total, subsequent get_schedule() calls must
return the cached value rather than re-reading the (potentially stale) sheet.
After clear_actual_times() the cache entry is removed.
"""
from datetime import time
from unittest.mock import patch

from app import sheets


ONDECK_ACT = "On Deck - Sunrise Collective"


class FakeSheet:
    def __init__(self, initial_screentime="0"):
        self.rows = [
            ["header"] * 8,
            ["header"] * 8,
            ["header"] * 8,
            ["header"] * 8,
            ["header"] * 8,
            ["", "", ONDECK_ACT, "14:00", "15:00", "", "", initial_screentime],
        ]

    def get_all_values(self):
        return self.rows

    def update_cell(self, row_num, col_num, value):
        self.rows[row_num - 1][col_num - 1] = str(value)


def setup_function():
    sheets._screentime_sessions.clear()
    sheets._screentime_totals.clear()


def teardown_function():
    sheets._screentime_sessions.clear()
    sheets._screentime_totals.clear()


def test_cache_populated_after_stop():
    fake_sheet = FakeSheet()

    with patch("app.sheets._get_sheet", return_value=fake_sheet):
        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 0, 0)
            sheets.start_screentime(ONDECK_ACT)

        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 0, 30)
            sheets.stop_screentime(ONDECK_ACT)

    assert sheets._screentime_totals[ONDECK_ACT] == 30


def test_cache_used_over_stale_sheet_read():
    """After stop writes 30s, sheet still shows 0 — get_schedule should return cached 30."""
    fake_sheet = FakeSheet(initial_screentime="0")

    with patch("app.sheets._get_sheet", return_value=fake_sheet):
        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 0, 0)
            sheets.start_screentime(ONDECK_ACT)

        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 0, 30)
            sheets.stop_screentime(ONDECK_ACT)

        # Simulate stale read: reset the sheet cell back to 0
        fake_sheet.rows[5][7] = "0"

        acts = sheets.get_schedule()

    act = next(a for a in acts if a.act_name == ONDECK_ACT)
    assert act.screentime_total_seconds == 30  # cache wins over stale sheet


def test_cache_accumulates_across_sessions():
    fake_sheet = FakeSheet()

    with patch("app.sheets._get_sheet", return_value=fake_sheet):
        # First session: 20s
        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 0, 0)
            sheets.start_screentime(ONDECK_ACT)
        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 0, 20)
            sheets.stop_screentime(ONDECK_ACT)

        # Second session: 10s
        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 1, 0)
            sheets.start_screentime(ONDECK_ACT)
        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 1, 10)
            sheets.stop_screentime(ONDECK_ACT)

    assert sheets._screentime_totals[ONDECK_ACT] == 30


def test_cache_cleared_by_clear_actual_times():
    fake_sheet = FakeSheet()

    with patch("app.sheets._get_sheet", return_value=fake_sheet):
        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 0, 0)
            sheets.start_screentime(ONDECK_ACT)
        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 0, 30)
            sheets.stop_screentime(ONDECK_ACT)

        assert ONDECK_ACT in sheets._screentime_totals

        sheets.clear_actual_times(ONDECK_ACT)

    assert ONDECK_ACT not in sheets._screentime_totals


def test_get_schedule_falls_back_to_sheet_when_no_cache():
    """Without a cache entry, get_schedule should read the sheet value."""
    fake_sheet = FakeSheet(initial_screentime="1:00:00")  # 3600s in sheet

    with patch("app.sheets._get_sheet", return_value=fake_sheet):
        acts = sheets.get_schedule()

    act = next(a for a in acts if a.act_name == ONDECK_ACT)
    assert act.screentime_total_seconds == 3600

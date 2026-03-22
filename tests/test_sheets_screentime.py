from datetime import time
from unittest.mock import patch

from app import sheets


ONDECK_ACT = "On Deck - Sunrise Collective"


class FakeSheet:
    def __init__(self):
        self.rows = [
            ["header"] * 8,
            ["header"] * 8,
            ["header"] * 8,
            ["header"] * 8,
            ["header"] * 8,
            ["", ONDECK_ACT, "", "14:00", "", "", "", "00:01:30"],
        ]

    def get_all_values(self):
        return self.rows

    def update_cell(self, row_num, col_num, value):
        self.rows[row_num - 1][col_num - 1] = str(value)


def setup_function():
    sheets._screentime_sessions.clear()


def teardown_function():
    sheets._screentime_sessions.clear()


def test_stop_screentime_accumulates_existing_hhmmss_total():
    fake_sheet = FakeSheet()

    with patch("app.sheets._get_sheet", return_value=fake_sheet):
        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 2, 0)
            sheets.start_screentime(ONDECK_ACT)

        with patch("app.sheets.datetime") as mock_dt:
            mock_dt.now.return_value.time.return_value = time(14, 2, 30)
            result = sheets.stop_screentime(ONDECK_ACT)

    assert result is not None
    assert result.screentime_total_seconds == 120
    assert fake_sheet.rows[5][7] == "120"

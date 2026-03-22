from app.sheets import _parse_screentime_seconds


# --- integer strings ---

def test_parse_integer_zero():
    assert _parse_screentime_seconds("0") == 0


def test_parse_integer_seconds():
    assert _parse_screentime_seconds("90") == 90


def test_parse_integer_large():
    assert _parse_screentime_seconds("3600") == 3600


# --- MM:SS strings (format stored by Google Sheets) ---

def test_parse_mmss_zero():
    assert _parse_screentime_seconds("0:00") == 0


def test_parse_mmss_seconds_only():
    assert _parse_screentime_seconds("0:45") == 45


def test_parse_mmss_minutes_and_seconds():
    assert _parse_screentime_seconds("1:30") == 90


def test_parse_mmss_large():
    assert _parse_screentime_seconds("60:00") == 3600


# --- edge cases ---

def test_parse_empty_string():
    assert _parse_screentime_seconds("") == 0


def test_parse_whitespace():
    assert _parse_screentime_seconds("  ") == 0


def test_parse_whitespace_around_value():
    assert _parse_screentime_seconds("  45  ") == 45


def test_parse_invalid_returns_zero():
    assert _parse_screentime_seconds("bad") == 0


def test_parse_invalid_mmss_returns_zero():
    assert _parse_screentime_seconds("a:bc") == 0

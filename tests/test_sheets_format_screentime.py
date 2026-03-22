from app.sheets import _format_screentime, _parse_screentime_seconds


# --- _format_screentime basic cases ---

def test_format_zero():
    assert _format_screentime(0) == "0:00:00"


def test_format_seconds_only():
    assert _format_screentime(45) == "0:00:45"


def test_format_one_minute():
    assert _format_screentime(60) == "0:01:00"


def test_format_minutes_and_seconds():
    assert _format_screentime(90) == "0:01:30"


def test_format_one_hour():
    assert _format_screentime(3600) == "1:00:00"


def test_format_hours_minutes_seconds():
    assert _format_screentime(3723) == "1:02:03"


def test_format_pads_minutes_and_seconds():
    assert _format_screentime(65) == "0:01:05"


def test_format_large_value():
    assert _format_screentime(7384) == "2:03:04"


# --- round-trip: format → parse ---

def test_roundtrip_zero():
    assert _parse_screentime_seconds(_format_screentime(0)) == 0


def test_roundtrip_seconds_only():
    assert _parse_screentime_seconds(_format_screentime(45)) == 45


def test_roundtrip_minutes_and_seconds():
    assert _parse_screentime_seconds(_format_screentime(90)) == 90


def test_roundtrip_one_hour():
    assert _parse_screentime_seconds(_format_screentime(3600)) == 3600


def test_roundtrip_hours_minutes_seconds():
    assert _parse_screentime_seconds(_format_screentime(3723)) == 3723


def test_roundtrip_large_value():
    assert _parse_screentime_seconds(_format_screentime(7384)) == 7384

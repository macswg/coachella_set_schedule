from datetime import time

from app.sheets import _parse_time


# --- HH:MM format ---

def test_parse_hhmm_basic():
    assert _parse_time("14:30") == time(14, 30, 0)


def test_parse_hhmm_midnight():
    assert _parse_time("00:00") == time(0, 0, 0)


def test_parse_hhmm_end_of_day():
    assert _parse_time("23:59") == time(23, 59, 0)


# --- HH:MM:SS format ---

def test_parse_hhmmss_basic():
    assert _parse_time("14:30:45") == time(14, 30, 45)


def test_parse_hhmmss_midnight():
    assert _parse_time("00:00:00") == time(0, 0, 0)


def test_parse_hhmmss_with_seconds():
    assert _parse_time("09:05:30") == time(9, 5, 30)


# --- H:MM AM/PM format ---

def test_parse_ampm_pm():
    assert _parse_time("2:30 PM") == time(14, 30, 0)


def test_parse_ampm_am():
    assert _parse_time("9:00 AM") == time(9, 0, 0)


def test_parse_ampm_noon():
    assert _parse_time("12:00 PM") == time(12, 0, 0)


def test_parse_ampm_midnight():
    assert _parse_time("12:00 AM") == time(0, 0, 0)


def test_parse_ampm_uppercase():
    assert _parse_time("5:30 PM") == time(17, 30, 0)


# --- H:MM:SS AM/PM format ---

def test_parse_ampm_with_seconds():
    assert _parse_time("5:30:15 PM") == time(17, 30, 15)


def test_parse_ampm_am_with_seconds():
    assert _parse_time("9:00:00 AM") == time(9, 0, 0)


# --- whitespace handling ---

def test_parse_leading_trailing_whitespace():
    assert _parse_time("  14:30  ") == time(14, 30, 0)


def test_parse_leading_whitespace_ampm():
    assert _parse_time("  5:30 PM  ") == time(17, 30, 0)


# --- edge cases that should return None ---

def test_parse_empty_string_returns_none():
    assert _parse_time("") is None


def test_parse_whitespace_only_returns_none():
    assert _parse_time("   ") is None


def test_parse_invalid_returns_none():
    assert _parse_time("not-a-time") is None


def test_parse_partial_time_returns_none():
    assert _parse_time("14") is None


def test_parse_none_like_string_returns_none():
    assert _parse_time("—") is None

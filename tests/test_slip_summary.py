"""Tests for app.slip.summarize_show (Phase 7)."""

from app.slip import summarize_show


def _payload(acts):
    return {"name": "T", "is_current": False, "is_archived": False, "acts": acts}


def test_empty_show_is_safe():
    s = summarize_show(_payload([]))
    assert s["act_count"] == 0
    assert s["pct_started"] == 0.0
    assert s["max_start_variance_seconds"] is None


def test_counts_by_category_prefer_sets():
    payload = _payload([
        {"act_name": "Load In", "category": "loadin", "scheduled_start": "10:00:00"},
        {"act_name": "Artist A", "category": "set", "scheduled_start": "11:00:00", "scheduled_end": "12:00:00",
         "actual_start": "11:05:00", "actual_end": "12:10:00"},
        {"act_name": "Artist B", "category": "set", "scheduled_start": "13:00:00",
         "actual_start": "13:02:00"},
    ])
    s = summarize_show(payload)
    assert s["act_count"] == 3
    assert s["set_count"] == 2
    assert s["started_count"] == 2
    assert s["completed_count"] == 1
    # 2 of 2 sets started
    assert s["pct_started"] == 100.0
    assert s["pct_completed"] == 50.0


def test_variance_computation():
    payload = _payload([
        {"act_name": "Artist", "category": "set", "scheduled_start": "11:00:00", "scheduled_end": "12:00:00",
         "actual_start": "11:05:00", "actual_end": "12:10:00"},
    ])
    s = summarize_show(payload)
    assert s["max_start_variance_seconds"] == 300
    assert s["max_end_variance_seconds"] == 600
    assert s["avg_start_variance_seconds"] == 300
    assert s["avg_end_variance_seconds"] == 600

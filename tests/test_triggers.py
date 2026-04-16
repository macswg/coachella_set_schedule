"""
Tests for the schedule-based recording trigger engine (app/triggers.py).

All tests call the internal helpers directly and mock recorder.start_recording
so no real Ki Pro connection is needed.
"""

from datetime import time
from unittest.mock import patch, MagicMock

import pytest

from app.models import Act
from app import triggers


def make_act(name, start_h, start_m, end_h=None, end_m=None, actual_start=None, actual_end=None):
    """Helper to build an Act with minimal boilerplate."""
    end = time(end_h, end_m) if end_h is not None else None
    return Act(
        act_name=name,
        scheduled_start=time(start_h, start_m),
        scheduled_end=end,
        actual_start=actual_start,
        actual_end=actual_end,
    )


@pytest.fixture(autouse=True)
def reset_trigger_state():
    """Clear in-memory trigger state between every test."""
    triggers._triggered.clear()
    triggers._active_reminders.clear()
    triggers.set_enabled(True)
    yield
    triggers._triggered.clear()
    triggers._active_reminders.clear()


# ---------------------------------------------------------------------------
# _normalize_act_start_secs
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_no_midnight_crossing(self):
        acts = [make_act("A", 20, 0, 21, 0), make_act("B", 21, 30, 22, 30)]
        norm = triggers._normalize_act_start_secs(acts)
        assert norm["A"] == 20 * 3600
        assert norm["B"] == 21 * 3600 + 30 * 60

    def test_midnight_crossing_bumped(self):
        acts = [
            make_act("Late", 23, 0, 23, 59),
            make_act("Post", 0, 30, 1, 30),   # crosses midnight
        ]
        norm = triggers._normalize_act_start_secs(acts)
        assert norm["Late"] == 23 * 3600
        assert norm["Post"] == 86400 + 30 * 60  # 86400 + 1800

    def test_multiple_post_midnight(self):
        acts = [
            make_act("A", 22, 0, 23, 0),
            make_act("B", 23, 0, 0, 0),   # ends at midnight
            make_act("C", 0, 0, 1, 0),    # crosses midnight
            make_act("D", 1, 0, 2, 0),
        ]
        norm = triggers._normalize_act_start_secs(acts)
        assert norm["A"] == 79200
        assert norm["B"] == 82800
        assert norm["C"] == 86400       # midnight bumped
        assert norm["D"] == 86400 + 3600  # 1am bumped

    def test_acts_within_one_hour_not_bumped(self):
        """An act that is only slightly earlier than previous (< 1h gap) is not bumped."""
        acts = [make_act("A", 23, 30, 0, 0), make_act("B", 23, 0, 23, 30)]
        norm = triggers._normalize_act_start_secs(acts)
        # B.start (82800) is only 30min before A.start (84600) — not a midnight cross
        assert norm["B"] == 82800


# ---------------------------------------------------------------------------
# check_and_fire — basic trigger behaviour
# ---------------------------------------------------------------------------

class TestCheckAndFire:
    def _fire(self, acts, now_time):
        """Call check_and_fire with a fixed 'now' time, mocking recorder."""
        with patch("app.recorder.start_recording") as mock_rec, \
             patch("app.triggers.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.time.return_value = now_time
            mock_dt.now.return_value = mock_now
            result = triggers.check_and_fire(acts)
        return result, mock_rec

    def test_fires_at_trigger_time(self):
        act = make_act("Set: Artist", 21, 0, 22, 0)
        result, mock_rec = self._fire([act], time(20, 55))  # 5 min before
        assert "Set: Artist" in result
        mock_rec.assert_called_once_with("Set: Artist")

    def test_does_not_fire_too_early(self):
        act = make_act("Set: Artist", 21, 0, 22, 0)
        result, mock_rec = self._fire([act], time(20, 54))  # 6 min before
        assert result == []
        mock_rec.assert_not_called()

    def test_fires_within_grace_period(self):
        """Trigger should still fire up to 1 hour after scheduled start."""
        act = make_act("Set: Artist", 21, 0, 22, 0)
        result, mock_rec = self._fire([act], time(21, 30))
        assert "Set: Artist" in result

    def test_does_not_fire_after_grace(self):
        act = make_act("Set: Artist", 21, 0, 22, 0)
        result, mock_rec = self._fire([act], time(22, 1))  # 1h1m after start
        assert result == []

    def test_does_not_double_fire(self):
        act = make_act("Set: Artist", 21, 0, 22, 0)
        self._fire([act], time(20, 55))
        # second poll at same time
        result, mock_rec = self._fire([act], time(20, 56))
        assert result == []
        mock_rec.assert_not_called()

    def test_skips_completed_act(self):
        act = make_act("Set: Artist", 21, 0, 22, 0,
                       actual_start=time(21, 0), actual_end=time(22, 0))
        result, _ = self._fire([act], time(20, 55))
        assert result == []

    def test_skips_loadin(self):
        act = make_act("Load In: Artist", 20, 0)
        result, _ = self._fire([act], time(19, 55))
        assert result == []

    def test_skips_ondeck(self):
        act = make_act("On Deck: Artist", 20, 0, 21, 0)
        result, _ = self._fire([act], time(19, 55))
        assert result == []

    def test_skips_changeover(self):
        act = make_act("Changeover", 20, 0, 20, 30)
        result, _ = self._fire([act], time(19, 55))
        assert result == []

    def test_skips_end_of_show(self):
        act = make_act("END OF SHOW", 23, 0)
        result, _ = self._fire([act], time(22, 55))
        assert result == []

    def test_prefix_filter_match(self):
        act = make_act("Set: Artist", 21, 0, 22, 0)
        with patch.object(triggers.settings, "RECORDING_ACT_PREFIX", "Set:"):
            result, mock_rec = self._fire([act], time(20, 55))
        assert "Set: Artist" in result

    def test_prefix_filter_no_match(self):
        act = make_act("Artist", 21, 0, 22, 0)
        with patch.object(triggers.settings, "RECORDING_ACT_PREFIX", "Set:"):
            result, mock_rec = self._fire([act], time(20, 55))
        assert result == []
        mock_rec.assert_not_called()


# ---------------------------------------------------------------------------
# check_and_fire — midnight crossing
# ---------------------------------------------------------------------------

class TestMidnightTriggers:
    def _fire(self, acts, now_time):
        with patch("app.recorder.start_recording") as mock_rec, \
             patch("app.triggers.datetime") as mock_dt:
            mock_now = MagicMock()
            mock_now.time.return_value = now_time
            mock_dt.now.return_value = mock_now
            result = triggers.check_and_fire(acts)
        return result, mock_rec

    def test_post_midnight_act_fires_at_correct_time(self):
        """An act starting at 1am should trigger at 12:55am, not at 10pm."""
        acts = [
            make_act("Late Act", 22, 0, 23, 0),
            make_act("Post Midnight", 1, 0, 2, 0),
        ]
        # Should not fire at 10pm (22:00)
        result, _ = self._fire(acts, time(22, 0))
        assert "Post Midnight" not in result

        # Should fire at 12:55am
        triggers._triggered.clear()
        result, mock_rec = self._fire(acts, time(0, 55))
        assert "Post Midnight" in result
        mock_rec.assert_called_with("Post Midnight")

    def test_post_midnight_now_secs_bumped(self):
        """At 1am with a post-midnight show, now_secs should be bumped so the
        1am act's trigger window is evaluated correctly."""
        acts = [
            make_act("Evening Act", 22, 0, 23, 0),
            make_act("Midnight Act", 0, 0, 1, 0),
            make_act("Late Act", 1, 30, 2, 30),
        ]
        # At 1:25am the Late Act trigger window should be open (5min before 1:30am)
        result, mock_rec = self._fire(acts, time(1, 25))
        assert "Late Act" in result

    def test_evening_act_does_not_fire_post_midnight(self):
        """A 10pm act should not re-trigger at 1am (outside grace window)."""
        acts = [
            make_act("Evening Act", 22, 0, 23, 0),
            make_act("Late Act", 1, 0, 2, 0),
        ]
        result, _ = self._fire(acts, time(1, 0))
        assert "Evening Act" not in result

    def test_midnight_act_fires_before_midnight(self):
        """Trigger for a midnight act (00:00) should fire at 23:55."""
        acts = [
            make_act("Evening Act", 22, 0, 23, 0),
            make_act("Midnight Act", 0, 0, 1, 0),
        ]
        result, mock_rec = self._fire(acts, time(23, 55))
        assert "Midnight Act" in result

    def test_midnight_act_is_last_act_grace_window(self):
        """When a 00:00 act is the last act, max_start == 86400 exactly.
        now_secs must still be bumped at 00:15 so the grace window is open.
        Regression: the old `max_start > 86400` check missed this edge case."""
        acts = [
            make_act("Evening Act", 22, 0, 23, 0),
            make_act("Midnight Act", 0, 0, 1, 0),  # last act — max_start == 86400
        ]
        # 15 min after midnight: should still be within the 1-hour grace window
        result, mock_rec = self._fire(acts, time(0, 15))
        assert "Midnight Act" in result
        mock_rec.assert_called_with("Midnight Act")

    def test_midnight_act_is_last_act_not_bumped_evening(self):
        """Evening acts should not fire at 00:15 even when max_start == 86400."""
        acts = [
            make_act("Evening Act", 22, 0, 23, 0),
            make_act("Midnight Act", 0, 0, 1, 0),
        ]
        # Fire once at correct time to trigger Evening Act
        self._fire(acts, time(21, 55))
        triggers._triggered.clear()
        # At 00:15 Evening Act must not re-trigger (its window closed at 23:00)
        result, _ = self._fire(acts, time(0, 15))
        assert "Evening Act" not in result

"""Tests for Act.is_preshow computed field."""

from datetime import time
import pytest
from app.models import Act


def make_act(name):
    return Act(act_name=name, scheduled_start=time(20, 0), scheduled_end=time(21, 0))


class TestIsPreshow:
    def test_is_preshow_true(self):
        assert make_act("Preshow: DJ Name").is_preshow is True

    def test_is_preshow_case_insensitive(self):
        assert make_act("preshow artist").is_preshow is True

    def test_is_preshow_mid_string(self):
        assert make_act("My Preshow Act").is_preshow is True

    def test_is_preshow_false_regular(self):
        assert make_act("Sunset Collective").is_preshow is False

    def test_is_preshow_false_loadin(self):
        act = Act(act_name="Load In - Main Stage", scheduled_start=time(18, 0))
        assert act.is_preshow is False

    def test_is_preshow_false_ondeck(self):
        assert make_act("On Deck: Sunrise").is_preshow is False

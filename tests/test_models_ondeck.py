from datetime import time
from app.models import Act


def make_act(name, **kwargs):
    defaults = dict(
        act_name=name,
        scheduled_start=time(12, 0),
    )
    defaults.update(kwargs)
    return Act(**defaults)


# --- is_ondeck ---

def test_is_ondeck_true():
    act = make_act("On Deck - Sunrise Collective")
    assert act.is_ondeck is True


def test_is_ondeck_case_insensitive():
    act = make_act("on deck - artist")
    assert act.is_ondeck is True


def test_is_ondeck_false_for_regular_act():
    act = make_act("Sunrise Collective", scheduled_end=time(13, 0))
    assert act.is_ondeck is False


def test_is_ondeck_false_for_loadin():
    act = make_act("Load In - Main Stage")
    assert act.is_ondeck is False


# --- is_loadin ---

def test_is_loadin_true():
    act = make_act("Load In - Main Stage")
    assert act.is_loadin is True


def test_is_loadin_case_insensitive():
    act = make_act("load in - stage")
    assert act.is_loadin is True


def test_is_loadin_false_for_regular_act():
    act = make_act("Sunrise Collective", scheduled_end=time(13, 0))
    assert act.is_loadin is False


def test_is_loadin_false_for_ondeck():
    act = make_act("On Deck - Sunrise Collective")
    assert act.is_loadin is False

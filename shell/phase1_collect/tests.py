import pytest

from config.project import Item
from phase1_collect.rules import HIGH, SAVED, parse_answer, route_after

WITH_FOLLOW_UP = Item(id="Q01", scale_min=0, scale_max=10, threshold=7)
WITHOUT_FOLLOW_UP = Item(id="Q02", scale_min=0, scale_max=10, threshold=None)


@pytest.mark.parametrize("raw, value", [("0", 0), ("7", 7), (" 10 ", 10)])
def test_parse_answer_accepts_the_scale(raw, value):
    assert parse_answer(WITH_FOLLOW_UP, raw) == value


@pytest.mark.parametrize("raw", ["-1", "11", "zeven", ""])
def test_parse_answer_refuses_everything_else(raw):
    with pytest.raises(ValueError):
        parse_answer(WITH_FOLLOW_UP, raw)


@pytest.mark.parametrize(
    "item, value, connector",
    [(WITH_FOLLOW_UP, 6, SAVED), (WITH_FOLLOW_UP, 7, HIGH), (WITHOUT_FOLLOW_UP, 10, SAVED)],
)
def test_route_after(item, value, connector):
    assert route_after(item, value) == connector


WORDS = Item(id="Q09", scale_min=1, scale_max=4, threshold=3, labels=("Not at all", "A little", "Quite a bit", "Very much"))


@pytest.mark.parametrize("raw, value", [("Not at all", 1), ("Quite a bit", 3), (" Very much ", 4), ("2", 2)])
def test_parse_answer_accepts_the_labels(raw, value):
    assert parse_answer(WORDS, raw) == value


def test_parse_answer_refuses_an_unknown_word():
    with pytest.raises(ValueError):
        parse_answer(WORDS, "Quite")

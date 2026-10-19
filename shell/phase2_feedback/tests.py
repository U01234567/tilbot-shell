import dataclasses

import pytest

from accounts.models import Participant
from accounts.session import SESSION_KEY
from bridge.tests import STUDY
from config.project import Feedback, FEEDBACK_TEXT_KEYS, Item, Scale
from phase2_feedback.scoring import scale_score, worth_discussing
from records.models import Answer

# Three scales scored as in the EORTC QLQ-C30 manual: items 1–4, and 1–7 for quality of life.
ITEMS = {
    "Q06": Item("Q06", 1, 4, None), "Q07": Item("Q07", 1, 4, None),
    "Q09": Item("Q09", 1, 4, None), "Q19": Item("Q19", 1, 4, None),
    "Q29": Item("Q29", 1, 7, None), "Q30": Item("Q30", 1, 7, None),
    "Q10": Item("Q10", 1, 4, None), "Q12": Item("Q12", 1, 4, None), "Q18": Item("Q18", 1, 4, None),
}


def scale(id, items, higher, reverse=False, threshold=None):
    return Scale(id, f"Name of {id}", tuple(items), higher, reverse, threshold)


ROLE = scale("role", ["Q06", "Q07"], "better", reverse=True, threshold=58)
PAIN = scale("pain", ["Q09", "Q19"], "worse", threshold=25)
QOL = scale("qol", ["Q29", "Q30"], "better")
FATIGUE = scale("fatigue", ["Q10", "Q12", "Q18"], "worse", threshold=39)


@pytest.mark.parametrize("scale, answers, score", [
    (ROLE, {"Q06": 2, "Q07": 2}, 66.7),  # manual: (1 - (2 - 1) / 3) × 100
    (PAIN, {"Q09": 2, "Q19": 3}, 50.0),  # manual: ((2.5 - 1) / 3) × 100
    (QOL, {"Q29": 5, "Q30": 6}, 75.0),  # manual: ((5.5 - 1) / 6) × 100
    (PAIN, {"Q09": 2}, 33.3),  # half of the items answered: the mean of those
])
def test_scale_score_follows_the_eortc_manual(scale, answers, score):
    assert round(scale_score(scale, ITEMS, answers), 1) == score


def test_scale_score_needs_half_of_the_items():
    assert scale_score(FATIGUE, ITEMS, {"Q10": 3}) is None
    assert scale_score(PAIN, ITEMS, {"Q01": 3}) is None


@pytest.mark.parametrize("scale, score, flagged", [
    (ROLE, 50, True), (ROLE, 66.7, False),  # higher is better: below the threshold
    (PAIN, 33.3, True), (PAIN, 16.7, False),  # higher is worse: above the threshold
    (QOL, 0, False),  # no threshold: never
])
def test_worth_discussing(scale, score, flagged):
    assert worth_discussing(scale, score) is flagged


FEEDBACK = Feedback(texts={key: f"<{key}>" for key in FEEDBACK_TEXT_KEYS}, scales=(ROLE, PAIN, QOL))


@pytest.fixture
def signed_in(client, db, settings):
    settings.STUDY = dataclasses.replace(STUDY, items=ITEMS, feedback=FEEDBACK)
    participant = Participant.objects.create(code="K7QM", age=50, gender="Other")
    session = client.session
    session[SESSION_KEY] = participant.pk
    session.save()
    return participant


def test_results_need_a_signed_in_participant(client, db, settings):
    settings.STUDY = dataclasses.replace(STUDY, items=ITEMS, feedback=FEEDBACK)
    assert client.get("/results").status_code == 404


def test_results_need_a_feedback_file(client, signed_in, settings):
    settings.STUDY = dataclasses.replace(STUDY, items=ITEMS)
    assert client.get("/results").status_code == 404


def answer_all(participant, **values):
    """Answer every item with 1 (so: no trouble, worst quality of life), except the ones given."""
    for item in ITEMS:
        Answer.objects.create(participant=participant, item=item, value=str(values.get(item, 1)))


def test_results_show_each_scale_with_the_latest_answers(client, signed_in):
    Answer.objects.create(participant=signed_in, item="Q09", value="1")
    answer_all(signed_in, Q09=4, Q06=2, Q07=2, Q29=4, Q30=4)  # this Q09 is the latest: it counts
    page = client.get("/results").content.decode()
    assert page.count("<hr>") == 3 and "Name of qol" in page
    assert page.count("&lt;worth_discussing&gt;") == 1  # pain: (4 + 1) / 2, not (1 + 1) / 2
    assert 'class="fill worth"' in page and page.count('class="fill fine"') == 1


def test_the_track_shows_where_a_score_is_worth_discussing(client, signed_in):
    answer_all(signed_in)
    page = client.get("/results").content.decode()
    assert '<rect class="worth-zone" x="0" y="0" width="58"' in page  # role: higher is better, below 58
    assert '<rect class="worth-zone" x="25" y="0" width="75"' in page  # pain: higher is worse, above 25


def test_no_results_before_every_item_is_answered(client, signed_in):
    Answer.objects.create(participant=signed_in, item="Q09", value="2")
    Answer.objects.create(participant=signed_in, item="Q19", value="2")
    assert "&lt;none&gt;" in client.get("/results").content.decode()


def test_bars_use_a_decimal_point_in_every_language(client, signed_in, settings):
    settings.LANGUAGE_CODE = "nl"
    answer_all(signed_in, Q09=2, Q19=2)
    assert 'width="33.33' in client.get("/results").content.decode()


def test_chat_page_offers_the_results_once_every_item_is_answered(client, signed_in, settings):
    settings.STUDY = dataclasses.replace(settings.STUDY, tilbot_project_id="1" * 32)
    Answer.objects.create(participant=signed_in, item="Q09", value="2")
    page = client.get("/chat").content.decode()
    assert "js/chat.js" in page and "data-results-open" not in page and 'data-done="false"' in page
    answer_all(signed_in)
    page = client.get("/chat").content.decode()
    assert "data-results-open" in page and 'data-done="true"' in page

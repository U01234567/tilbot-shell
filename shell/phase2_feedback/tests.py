import dataclasses

import pytest

from accounts.models import Participant
from accounts.session import SESSION_KEY
from bridge.tests import STUDY
from config.project import Feedback, FEEDBACK_TEXT_KEYS, Item, Scale
from bridge.tokens import make_token
from phase2_feedback import story
from phase2_feedback.scoring import scale_score, worth_discussing
from records.models import Answer, FeedbackShown

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
    assert page.count('<section class="scale') == 3 and "Name of qol" in page
    assert page.count('class="status worth"') == 1  # pain: (4 + 1) / 2, not (1 + 1) / 2
    assert page.count('class="status fine"') == 1  # role; qol has no threshold, so no word
    assert 'class="fill worth"' in page and page.count('class="fill fine"') == 1


def test_each_bar_lists_the_questions_and_answers_it_is_based_on(client, signed_in, settings):
    items = {**ITEMS, "Q09": Item("Q09", 1, 4, None, ("No", "A bit", "Quite", "Very"), "Any pain?")}
    settings.STUDY = dataclasses.replace(settings.STUDY, items=items)
    answer_all(signed_in, Q09=3, Q19=2)
    page = client.get("/results").content.decode()
    assert "<li>Any pain? <b>Quite</b></li><li>Q19 <b>2</b></li>" in page  # no text, no labels: id and number


def test_every_line_runs_from_worse_to_better(client, signed_in):
    answer_all(signed_in, Q06=2, Q07=2)  # role 66.7, pain 0 (no pain: the best), qol 0 (the worst)
    page = client.get("/results").content.decode()
    assert '<rect class="fine-zone" x="58"' in page and 'cx="66.66' in page  # role: higher is better, as is
    assert '<rect class="fine-zone" x="75"' in page and 'cx="100.0"' in page  # pain: turned around
    assert '<circle class="fill" cx="0.0"' in page  # qol: no threshold, a neutral dot


def test_no_results_before_every_item_is_answered(client, signed_in):
    Answer.objects.create(participant=signed_in, item="Q09", value="2")
    Answer.objects.create(participant=signed_in, item="Q19", value="2")
    assert "&lt;none&gt;" in client.get("/results").content.decode()


def test_bars_use_a_decimal_point_in_every_language(client, signed_in, settings):
    settings.LANGUAGE_CODE = "nl"
    answer_all(signed_in, Q09=2, Q19=2)
    assert 'cx="66.66' in client.get("/results").content.decode()  # pain 33.3, turned around


@pytest.mark.parametrize("show, panel", [("panel", True), ("both", True), ("chat", False)])
def test_chat_page_has_the_panel_only_when_the_study_shows_it(client, signed_in, settings, show, panel):
    feedback = dataclasses.replace(FEEDBACK, show=show)
    settings.STUDY = dataclasses.replace(settings.STUDY, tilbot_project_id="1" * 32, feedback=feedback)
    page = client.get("/chat").content.decode()
    assert ('id="results"' in page) is panel
    assert ("data-results-open hidden" in page) is panel  # chat.js shows it once the panel opened on this visit


def test_chat_page_knows_when_the_questionnaire_is_done(client, signed_in, settings):
    settings.STUDY = dataclasses.replace(settings.STUDY, tilbot_project_id="1" * 32)
    Answer.objects.create(participant=signed_in, item="Q09", value="2")
    assert 'data-done="false"' in client.get("/chat").content.decode()
    answer_all(signed_in)
    assert 'data-done="true"' in client.get("/chat").content.decode()


# Feedback in the chat (story.py, and /bridge/feedback which Tilbot calls).

TOLD = (
    dataclasses.replace(ROLE, story={"fine": "{name} went fine ({answers}).", "worth": "{name}: worth a talk ({Q06}, {Q07})."}),
    dataclasses.replace(PAIN, story={"fine": "Little {name}.", "worth": "{name} bothered you ({answers})."}),
    dataclasses.replace(QOL, story={"neutral": "Your {name}: {Q29} and {Q30}."}),
)
LABELS = ("No", "A bit", "Quite", "Very")
TOLD_ITEMS = {**ITEMS, "Q06": Item("Q06", 1, 4, None, LABELS), "Q07": Item("Q07", 1, 4, None, LABELS)}
CHAT = dataclasses.replace(FEEDBACK, scales=TOLD, show="chat", story={"opening": "Thanks!", "closing": "Bye."})


def test_story_fills_in_each_scales_sentence():
    answers = {"Q06": 3, "Q07": 2, "Q09": 1, "Q19": 1, "Q29": 5, "Q30": 6}  # role 50: worth; pain 0: fine
    assert story.story(CHAT, TOLD_ITEMS, answers) == (
        "Thanks!\n\nName of role: worth a talk (quite, a bit).\n\nLittle Name of pain.\n\nYour Name of qol: 5 and 6.\n\nBye."
    )


def test_chart_draws_every_line_from_worse_to_better():
    scales = (dataclasses.replace(PAIN, ends=("Much pain", "No pain")), QOL)
    feedback = dataclasses.replace(CHAT, scales=scales)
    assert story.chart(feedback, ITEMS, {"Q09": 2, "Q19": 3, "Q29": 7, "Q30": 7}).splitlines() == [
        "Name of pain: <worth_discussing>",  # 50, above the threshold of 25
        "[[line Much pain|No pain|50.0|75.0|worth]]",  # turned around: higher is worse
        "Name of qol",  # no threshold, no word
        "[[line ||100.0||neutral]]",
    ]


def ask_feedback(client, participant, part, secret="test-secret"):
    return client.post("/bridge/feedback", {"participant_id": make_token(participant.pk), "part": part, "bridge_secret": secret})


@pytest.fixture
def bridge(settings):
    settings.BRIDGE_SECRET = "test-secret"


def test_feedback_waits_for_every_answer(client, signed_in, bridge):
    Answer.objects.create(participant=signed_in, item="Q09", value="2")
    assert ask_feedback(client, signed_in, "story").status_code == 400  # Tilbot follows "else"
    assert ask_feedback(client, signed_in, "story", secret="wrong").status_code == 403


def test_feedback_in_the_panel_is_noted_and_opens_it(client, signed_in, bridge):
    answer_all(signed_in)
    assert ask_feedback(client, signed_in, "story").json() == {"intent": "panel"}
    assert list(FeedbackShown.objects.values_list("participant", "show")) == [(signed_in.pk, "panel")]


@pytest.mark.parametrize("show", ["chat", "both"])
def test_feedback_in_the_chat_tells_the_story_then_the_chart(client, signed_in, bridge, settings, show):
    settings.STUDY = dataclasses.replace(settings.STUDY, items=TOLD_ITEMS, feedback=dataclasses.replace(CHAT, show=show))
    answer_all(signed_in)
    told = ask_feedback(client, signed_in, "story").json()
    assert told["intent"] == "chat" and told["connector_label"].startswith("Thanks!")
    drawn = ask_feedback(client, signed_in, "chart").json()
    assert drawn["intent"] == show and "[[line " in drawn["connector_label"]  # "both" also opens the panel
    assert FeedbackShown.objects.get().show == show

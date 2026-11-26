import dataclasses
import time

import pytest
from django.core import signing
from django.db import connection

from accounts.models import Participant
from accounts.session import SESSION_KEY
from bridge.tokens import fernet, make_token, read_token
from config.project import Condition, Item, Narrative, Study
from phase2_feedback import narrative as narratives
from records.models import Answer, Narrative as Told, TranscriptLine

SECRET = "test-secret"
STUDY = Study(
    name="Test",
    language="en",
    time_zone="UTC",
    transcripts=True,
    tilbot_project_id="0" * 32,
    age_min=1,
    age_max=150,
    genders=("Other",),
    texts={},
    items={"Q01": Item(id="Q01", scale_min=0, scale_max=10, threshold=7)},
)


@pytest.fixture(autouse=True)
def study(settings):
    settings.STUDY = STUDY
    settings.BRIDGE_SECRET = SECRET


@pytest.fixture
def participant(db):
    return Participant.objects.create(code="K7QM", age=50, gender="Other")


def post_answer(client, participant, answer, secret=SECRET):
    return client.post("/bridge/save", {
        "participant_id": make_token(participant.pk),
        "item": "Q01",
        "user_input": answer,
        "bridge_secret": secret,
    })


@pytest.mark.parametrize("answer, connector", [("6", "saved"), ("7", "high")])
def test_save_stores_the_answer_and_names_the_connector(client, participant, answer, connector):
    response = post_answer(client, participant, answer)
    assert response.json() == {"intent": connector}
    assert Answer.objects.get().value == answer


def test_answer_is_encrypted_in_the_database(client, participant):
    post_answer(client, participant, "6")
    with connection.cursor() as cursor:
        cursor.execute("SELECT value FROM records_answer")
        assert cursor.fetchone()[0] != "6"


def test_answer_off_the_scale_is_refused_so_tilbot_asks_again(client, participant):
    response = post_answer(client, participant, "11")
    assert response.status_code == 400
    assert not Answer.objects.exists()


def test_wrong_secret_is_refused(client, participant):
    response = post_answer(client, participant, "6", secret="wrong")
    assert response.status_code == 403
    assert not Answer.objects.exists()


def test_forged_token_is_refused(client, participant):
    response = client.post("/bridge/save", {
        "participant_id": "1:forged",
        "item": "Q01",
        "user_input": "6",
        "bridge_secret": SECRET,
    })
    assert response.status_code == 400


def test_chat_without_a_linked_project_says_so(client, participant):
    session = client.session
    session[SESSION_KEY] = participant.pk
    session.save()
    response = client.get("/chat")
    assert "No Tilbot project is linked yet" in response.content.decode()


def post_log(client, participant):
    return client.post("/bridge/log", {
        "participant_id": make_token(participant.pk),
        "conversation": "c1", "seq": "0", "event": "message_user", "detail": "hello", "bridge_secret": SECRET,
    })


def test_transcripts_are_kept_when_the_study_says_so(client, participant):
    assert post_log(client, participant).status_code == 204
    assert TranscriptLine.objects.get().text == "hello"


def test_transcripts_are_dropped_when_the_study_says_no(client, participant, settings):
    settings.STUDY = dataclasses.replace(STUDY, transcripts=False)
    assert post_log(client, participant).status_code == 204
    assert not TranscriptLine.objects.exists()


def test_chat_token_hides_the_row_number_and_refuses_tampering():
    token = make_token(4321)
    assert "4321" not in token and read_token(token) == 4321
    with pytest.raises(signing.BadSignature):
        read_token(token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1])


def test_chat_token_expires_with_the_session():
    old = fernet().encrypt_at_time(b"7", int(time.time()) - 13 * 60 * 60)
    with pytest.raises(signing.BadSignature):
        read_token(old.decode())


def test_chat_page_asks_before_signing_out(client, participant, settings):
    settings.STUDY = dataclasses.replace(STUDY, tilbot_project_id="1" * 32, texts={"sign_out_check": "Really leave?", "stay": "Stay"})
    session = client.session
    session[SESSION_KEY] = participant.pk
    session.save()
    page = client.get("/chat").content.decode()
    assert 'id="sign-out-check"' in page and "Really leave?" in page and "js/chat.js" in page


def post_status(client, participant, secret=SECRET):
    return client.post("/bridge/status", {"participant_id": make_token(participant.pk), "bridge_secret": secret})


def test_status_tells_tilbot_whether_the_questionnaire_is_done(client, participant):
    assert post_status(client, participant).json() == {"intent": "new"}
    Answer.objects.create(participant=participant, item="Q01", value="3")  # STUDY has one item
    assert post_status(client, participant).json() == {"intent": "returning"}
    assert post_status(client, participant, secret="wrong").status_code == 403


def test_chat_shows_tilbots_header(client, participant, settings):
    settings.STUDY = dataclasses.replace(STUDY, tilbot_project_id="1" * 32)
    session = client.session
    session[SESSION_KEY] = participant.pk
    session.save()
    assert "show_header" not in client.get("/chat").content.decode()


def test_each_answer_belongs_to_the_participants_round(client, participant):
    post_answer(client, participant, "3")
    participant.round = 2
    participant.save()
    assert post_status(client, participant).json() == {"intent": "new"}  # round 2 has no answers yet
    post_answer(client, participant, "4")
    assert list(Answer.objects.order_by("pk").values_list("round", flat=True)) == [1, 2]
    assert post_status(client, participant).json() == {"intent": "returning"}


NARRATIVE = Narrative(
    server="ollama", url="http://ollama:11434", model="m", prompt="{name}|{answers}|{story_so_far}",
    names=("Jef", "Sara", "Noah"), fallback="Thank you.",
    conditions=(Condition(id="per_round", memory="round", name="cycle"), Condition(id="ongoing", memory="all", name="fixed")),
)


@pytest.fixture
def model(settings, monkeypatch):
    """The language model, replaced: it answers with the prompt it got, so a test can read the prompt."""
    settings.STUDY = dataclasses.replace(STUDY, narrative=NARRATIVE)
    monkeypatch.setattr(narratives, "ask", lambda narrative, prompt: f"Story: {prompt}")


def post_narrative(client, participant):
    return client.post("/bridge/narrative", {"participant_id": make_token(participant.pk), "bridge_secret": SECRET})


def finish_round(client, participant, number, answer="3"):
    participant.round = number
    participant.save()
    post_answer(client, participant, answer)
    return post_narrative(client, participant).json()["connector_label"]


def test_narrative_waits_for_the_whole_round(client, participant, model):
    assert post_narrative(client, participant).status_code == 400


def test_per_round_condition_takes_the_next_name_and_only_this_round(client, participant, model):
    participant.condition = "per_round"
    first = finish_round(client, participant, 1)
    second = finish_round(client, participant, 2, answer="4")
    assert first.startswith("Story: Jef|") and second.startswith("Story: Sara|")
    assert "- Q01: 4|(none yet)" in second
    assert finish_round(client, participant, 4).startswith("Story: Jef|")  # three names: round 4 starts over


def test_ongoing_condition_keeps_its_name_and_continues_the_story(client, participant, model):
    participant.condition, participant.character = "ongoing", "Noah"
    first = finish_round(client, participant, 1)
    second = finish_round(client, participant, 2, answer="4")
    assert second.startswith("Story: Noah|- Q01: 4|") and second.endswith(first)


def test_the_same_round_gets_the_same_story(client, participant, model):
    participant.condition = "per_round"
    first = finish_round(client, participant, 1)
    assert post_narrative(client, participant).json()["connector_label"] == first
    assert Told.objects.count() == 1


def test_a_failing_model_gives_the_fallback_and_says_so(client, participant, model, monkeypatch):
    def fails(narrative, prompt):
        raise OSError("timed out")
    monkeypatch.setattr(narratives, "ask", fails)
    participant.condition = "per_round"
    assert finish_round(client, participant, 1) == "Thank you."
    assert Told.objects.get().generated is False


def test_a_long_story_is_cut_off():
    assert narratives.cut("one two three four", 2) == "one two …"

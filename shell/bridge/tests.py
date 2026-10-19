import dataclasses
import time

import pytest
from django.core import signing
from django.db import connection

from accounts.models import Participant
from accounts.session import SESSION_KEY
from bridge.tokens import fernet, make_token, read_token
from config.project import Item, Study
from records.models import Answer, TranscriptLine

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

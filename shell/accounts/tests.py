import pytest

from accounts.codes import ALPHABET, LENGTH, new_code, normalize
from accounts.models import Attempt, Participant
from accounts.views import FAILED_SIGN_INS_ALLOWED


def test_new_code_uses_only_the_alphabet():
    code = new_code()
    assert len(code) == LENGTH
    assert set(code) <= set(ALPHABET)


@pytest.mark.parametrize("typed, stored", [(" k7qm ", "K7QM"), ("o1il", "0111")])
def test_normalize(typed, stored):
    assert normalize(typed) == stored


@pytest.mark.django_db
def test_sign_up_creates_the_participant_with_the_shown_code(client, settings):
    client.get("/sign-up")
    shown = client.session["new_code"]
    response = client.post("/sign-up", {"age": settings.STUDY.age_min, "gender": settings.STUDY.genders[0]})
    assert response.status_code == 302
    assert Participant.objects.get().code == shown


@pytest.mark.django_db
def test_known_code_signs_in(client):
    Participant.objects.create(code="K7QM", age=50, gender="Other")
    response = client.post("/sign-in", {"code": "k7qm"})
    assert response.status_code == 302
    assert response.url == "/chat"


@pytest.mark.django_db
def test_unknown_code_gets_the_vague_message(client, settings):
    response = client.post("/sign-in", {"code": "ZZZZ"})
    assert settings.STUDY.texts["wrong_id"] in response.content.decode()


@pytest.mark.django_db
def test_too_many_failed_sign_ins_block_the_address(client):
    Attempt.objects.bulk_create(
        [Attempt(kind=Attempt.Kind.FAILED_SIGN_IN, ip="127.0.0.1") for _ in range(FAILED_SIGN_INS_ALLOWED)]
    )
    response = client.post("/sign-in", {"code": "ZZZZ"})
    assert response.status_code == 429

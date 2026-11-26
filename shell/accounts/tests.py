from datetime import timedelta

import dataclasses

import pytest
from django.conf import settings
from django.utils import timezone

from accounts.codes import ALPHABET, LENGTH, new_code, normalize
from accounts.models import Attempt, Participant
from accounts.views import FAILED_SIGN_INS_ALLOWED, WINDOW, assigned
from config.project import Condition, Narrative

# The sign-up and sign-in pages exist only for a study with codes, not for one that signs in by link.
with_codes = pytest.mark.skipif(settings.STUDY.by_link, reason="this study signs in by the ID in the link")


def test_new_code_uses_only_the_alphabet():
    code = new_code()
    assert len(code) == LENGTH
    assert set(code) <= set(ALPHABET)


@pytest.mark.parametrize("typed, stored", [(" k7qm ", "K7QM"), ("o1il", "0111")])
def test_normalize(typed, stored):
    assert normalize(typed) == stored


@with_codes
@pytest.mark.django_db
def test_sign_up_creates_the_participant_with_the_shown_code(client, settings):
    client.get("/sign-up")
    shown = client.session["new_code"]
    response = client.post("/sign-up", {"age": settings.STUDY.age_min, "gender": settings.STUDY.genders[0]})
    assert response.status_code == 302
    assert Participant.objects.get().code == shown


@with_codes
@pytest.mark.django_db
def test_known_code_signs_in(client):
    Participant.objects.create(code="K7QM", age=50, gender="Other")
    response = client.post("/sign-in", {"code": "k7qm"})
    assert response.status_code == 302
    assert response.url == "/chat"


@with_codes
@pytest.mark.django_db
def test_unknown_code_gets_the_vague_message(client, settings):
    response = client.post("/sign-in", {"code": "ZZZZ"})
    assert settings.STUDY.texts["wrong_id"] in response.content.decode()


@with_codes
@pytest.mark.django_db
def test_too_many_failed_sign_ins_block_the_address(client):
    Attempt.objects.bulk_create(
        [Attempt(kind=Attempt.Kind.FAILED_SIGN_IN, ip="127.0.0.1") for _ in range(FAILED_SIGN_INS_ALLOWED)]
    )
    response = client.post("/sign-in", {"code": "ZZZZ"})
    assert response.status_code == 429


@with_codes
@pytest.mark.django_db
def test_old_attempts_are_forgotten(client):
    Attempt.objects.create(kind=Attempt.Kind.FAILED_SIGN_IN, ip="127.0.0.1")
    Attempt.objects.update(at=timezone.now() - WINDOW - timedelta(minutes=1))  # auto_now_add ignores a given time
    client.post("/sign-in", {"code": "ZZZZ"})
    assert Attempt.objects.count() == 1


NARRATIVE = Narrative(
    server="ollama", url="http://ollama:11434", model="m", prompt="{name}", names=("Jef", "Sara"), fallback="Thanks.",
    conditions=(Condition(id="per_round", memory="round", name="cycle"), Condition(id="ongoing", memory="all", name="fixed")),
)


@pytest.fixture
def by_link(settings):
    settings.STUDY = dataclasses.replace(settings.STUDY, by_link=True, repeat=True, texts={**settings.STUDY.texts, "open_from_link": "Open the link."})


@pytest.mark.django_db
def test_a_new_id_in_the_link_is_a_new_participant_signed_in(client, by_link):
    response = client.get("/?id=mpath-123")
    assert response.url == "/chat"
    assert Participant.objects.get().code == "mpath-123"


@pytest.mark.django_db
def test_a_known_id_signs_in_and_starts_a_new_round(client, by_link):
    client.get("/?id=mpath-123")
    client.get("/?id=mpath-123")
    assert Participant.objects.get().round == 2


@pytest.mark.django_db
def test_without_repeat_the_round_stays(client, by_link, settings):
    settings.STUDY = dataclasses.replace(settings.STUDY, repeat=False)
    client.get("/?id=mpath-123")
    client.get("/?id=mpath-123")
    assert Participant.objects.get().round == 1


@pytest.mark.django_db
def test_without_a_usable_id_nobody_is_signed_in(client, by_link):
    assert "Open the link." in client.get("/?id=<script>").content.decode()
    assert client.get("/sign-up").url == "/"
    assert not Participant.objects.exists()


@pytest.mark.django_db
def test_conditions_stay_balanced_and_a_fixed_one_keeps_one_name(settings):
    settings.STUDY = dataclasses.replace(settings.STUDY, narrative=NARRATIVE)
    for number in range(6):
        Participant.objects.create(code=f"P{number}", **assigned())
    assert sorted(Participant.objects.values_list("condition", flat=True)) == ["ongoing"] * 3 + ["per_round"] * 3
    assert set(Participant.objects.filter(condition="ongoing").values_list("character", flat=True)) <= {"Jef", "Sara"}
    assert set(Participant.objects.filter(condition="per_round").values_list("character", flat=True)) == {""}

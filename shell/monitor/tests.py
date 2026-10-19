import csv
import dataclasses
import io
import sys
import zipfile

import pytest
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from accounts.models import Participant
from accounts.session import SESSION_KEY
from config.project import Feedback, Item, Scale
from monitor.management.commands.researcher import add_researcher
from records.models import Answer, Question


@pytest.fixture
def researcher(client, db):
    user = User.objects.create_user("researcher", password="test-only")
    client.force_login(user)
    return user


@pytest.fixture
def data(db):
    first = Participant.objects.create(code="AAAA", age=30, gender="Other")
    second = Participant.objects.create(code="BBBB", age=40, gender="Other")
    Answer.objects.create(participant=second, item="Q01", value="7")
    Answer.objects.create(participant=first, item="Q01", value="3")


def csv_rows(response, name):
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    return list(csv.reader(io.StringIO(archive.read(name).decode())))


@pytest.mark.django_db
def test_researcher_pages_need_a_login(client):
    assert client.get("/researcher/").status_code == 302
    assert client.post("/researcher/export", {"codes": "with"}).status_code == 302


def test_overview_counts(client, researcher, data):
    page = client.get("/researcher/").content.decode()
    assert "<td>2</td>" in page


def test_export_without_codes_numbers_participants_by_sign_up(client, researcher, data):
    response = client.post("/researcher/export", {"codes": "without"})
    assert csv_rows(response, "participants.csv")[1][0] == "1"
    assert csv_rows(response, "answers.csv")[1][:3] == ["2", "Q01", "7"]
    assert "AAAA" not in str(csv_rows(response, "participants.csv"))


def test_export_with_codes_carries_the_code(client, researcher, data):
    response = client.post("/researcher/export", {"codes": "with"})
    assert csv_rows(response, "answers.csv")[2][:3] == ["AAAA", "Q01", "3"]


def test_export_times_are_in_the_study_time_zone(client, researcher, data, settings):
    settings.TIME_ZONE = "Europe/Amsterdam"
    response = client.post("/researcher/export", {"codes": "without"})
    assert not csv_rows(response, "participants.csv")[1][3].endswith("+00:00")


def test_researcher_command_makes_the_account_when_tilbot_accepts(db):
    assert add_researcher("jonas", "a-long-test-password", tilbot_account=lambda name, password: "OK") == "OK"
    assert User.objects.get(username="jonas").check_password("a-long-test-password")


def test_researcher_command_refuses_a_weak_password_before_asking_tilbot(db):
    with pytest.raises(CommandError, match="too short"):
        add_researcher("jonas", "short", tilbot_account=lambda name, password: pytest.fail("Tilbot was asked"))
    assert not User.objects.exists()


def test_researcher_command_changes_nothing_when_tilbot_refuses(db):
    with pytest.raises(CommandError, match="NOK"):
        add_researcher("jonas", "a-long-test-password", tilbot_account=lambda name, password: "NOK")
    assert not User.objects.exists()


def test_export_has_the_scores_of_the_results(client, researcher, data, settings):
    pain = Scale("pain", "Pain", ("Q01",), "worse", False, 50)
    items = {"Q01": Item("Q01", 0, 10, None)}
    settings.STUDY = dataclasses.replace(settings.STUDY, items=items, feedback=Feedback(texts={}, scales=(pain,)))
    rows = csv_rows(client.post("/researcher/export", {"codes": "without"}), "scores.csv")
    assert rows == [["participant", "scale", "score", "worth_discussing"], ["1", "pain", "30.0", "False"], ["2", "pain", "70.0", "True"]]


def test_export_has_the_questions_asked(client, researcher, data):
    Question.objects.create(participant=Participant.objects.get(code="AAAA"), text="Can I stop?", entry="stop")
    rows = csv_rows(client.post("/researcher/export", {"codes": "with"}), "questions.csv")
    assert rows[0] == ["participant", "question", "entry", "at"]
    assert rows[1][:3] == ["AAAA", "Can I stop?", "stop"]


def test_remove_needs_a_login(client, db):
    assert client.post("/researcher/remove", {"code": "AAAA"}).status_code == 302


def test_remove_shows_what_goes_before_deleting(client, researcher, data):
    page = client.post("/researcher/remove", {"code": "aaaa"}).content.decode()
    assert "Delete AAAA for good" in page and "<td>1</td>" in page
    assert Participant.objects.filter(code="AAAA").exists()


def test_remove_says_so_for_an_unknown_code(client, researcher, data):
    assert "No participant has the code ZZZZ" in client.post("/researcher/remove", {"code": "ZZZZ"}).content.decode()


def test_remove_deletes_one_participant_with_their_data_and_sessions(client, researcher, data):
    first = Participant.objects.get(code="AAAA")
    Question.objects.create(participant=first, text="Can I stop?", entry="stop")
    participant_browser = Client()
    session = participant_browser.session
    session[SESSION_KEY] = first.pk
    session.save()
    client.post("/researcher/remove", {"code": "AAAA", "confirm": "AAAA"})
    assert not Participant.objects.filter(code="AAAA").exists()
    assert not Question.objects.exists() and Answer.objects.count() == 1  # BBBB's answer stays
    assert not Session.objects.filter(session_key=session.session_key).exists()


def test_erase_needs_the_study_name(data):
    with pytest.raises(CommandError, match="Nothing deleted"):
        call_command("erase", "not the name")
    assert Participant.objects.count() == 2


def test_erase_deletes_every_participant_but_keeps_researchers(researcher, data, settings):
    call_command("erase", settings.STUDY.name)
    assert not Participant.objects.exists() and not Answer.objects.exists()
    assert User.objects.filter(username="researcher").exists()


def test_backup_cipher_round_trip(monkeypatch):
    def run(direction, data):
        out = io.BytesIO()
        monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(data)))
        monkeypatch.setattr("sys.stdout", io.TextIOWrapper(out))
        call_command("backup_cipher", direction)
        sys.stdout.flush()
        return out.getvalue()
    sealed = run("encrypt", b"\x00binary dump\xff")
    assert b"binary dump" not in sealed
    assert run("decrypt", sealed) == b"\x00binary dump\xff"
    with pytest.raises(CommandError, match="not made with the FIELD_ENCRYPTION_KEY"):
        run("decrypt", b"something else")

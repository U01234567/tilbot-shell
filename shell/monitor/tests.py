import csv
import io
import zipfile

import pytest
from django.contrib.auth.models import User
from django.core.management.base import CommandError

from accounts.models import Participant
from monitor.management.commands.researcher import add_researcher
from records.models import Answer


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

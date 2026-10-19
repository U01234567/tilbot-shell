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
from monitor import system
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


# The system page (system.py). Docker itself isn't there in the tests: read_docker is replaced.

@pytest.mark.parametrize("state, status, health", [
    ("running", "Up 2 hours (healthy)", "up"),
    ("running", "Up 5 seconds (health: starting)", "starting"),
    ("running", "Up 3 minutes (unhealthy)", "down"),
    ("running", "Up 3 minutes", "up"),  # no health check: running is all Docker knows
    ("exited", "Exited (1) 2 minutes ago", "down"),
    ("restarting", "Restarting (1) 4 seconds ago", "down"),
])
def test_health_from_dockers_status(state, status, health):
    assert system.health(state, status) == health


def test_usage_as_docker_stats_shows_it():
    stats = {
        "cpu_stats": {"cpu_usage": {"total_usage": 300}, "system_cpu_usage": 2000, "online_cpus": 4},
        "precpu_stats": {"cpu_usage": {"total_usage": 100}, "system_cpu_usage": 1000},
        "memory_stats": {"usage": 5 * 2**20, "stats": {"inactive_file": 2**20}},
    }
    assert system.usage(stats) == {"cpu": 80.0, "memory": 4.0}  # 200 / 1000 × 4 cores × 100; 4 MB
    assert system.usage(None) == {"cpu": None, "memory": None}


def test_log_text_joins_dockers_pieces():
    def piece(stream, text):
        return bytes([stream, 0, 0, 0]) + len(text).to_bytes(4, "big") + text
    assert system.log_text(piece(1, b"started\n") + piece(2, b"warning \xc3\xa9\n")) == "started\nwarning é\n"


def test_arrows_run_from_box_to_box():
    assert system.arrow("browser", "caddy") == (150, 156, 190, 156)  # right side to left side
    assert system.arrow("tilbot-backend", "shell") == (455, 128, 455, 84)  # straight up in one column


def test_every_link_joins_two_components():
    assert {key for link in system.LINKS for key in link} == set(system.COMPONENTS)


def test_system_page_needs_a_login(client, db):
    assert client.get("/researcher/system").status_code == 302


def test_system_page_shows_what_docker_says(client, researcher, monkeypatch, settings):
    settings.STUDY = dataclasses.replace(settings.STUDY, knowledge=None)
    settings.LANGUAGE_CODE = "nl"  # a decimal point all the same: the researcher pages are English
    running = {"status": "Up 1 hour (healthy)", "health": "up", "log": "listening <on> 8000", "cpu": 1.5, "memory": 54.2}
    monkeypatch.setattr(system, "read_docker", lambda: {"shell": running})
    page = client.get("/researcher/system").content.decode()
    assert '<g class="node up">' in page and "1.5%" in page and "54 MB" in page
    assert "listening &lt;on&gt; 8000" in page  # log lines are text, never HTML
    assert "not used: the study has no knowledge.xlsx" in page  # the intent service without a knowledge base
    assert "no container: python start_shell.py up" in page  # db, among others


def test_system_page_says_when_docker_cant_be_read(client, researcher, monkeypatch):
    def unreachable():
        raise OSError("docker-proxy: name not known")
    monkeypatch.setattr(system, "read_docker", unreachable)
    page = client.get("/researcher/system").content.decode()
    assert "Docker can't be read: docker-proxy: name not known" in page and '<g class="node unknown">' in page

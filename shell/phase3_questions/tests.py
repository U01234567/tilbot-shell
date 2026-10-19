import dataclasses

import openpyxl
import pytest

from accounts.models import Participant
from bridge.tests import SECRET, STUDY
from bridge.tokens import make_token
from config.project import Entry, load_knowledge
from phase3_questions import matching
from records.models import Question

COLUMNS = ["id", "topic", "question", "phrasings", "answer", "link"]
INFO = Entry("info", "Information", ("Where can I read more?", "Is there a website?"), "On the study's website.", "https://example.org/info")
STOP = Entry("stop", "Taking part", ("Can I stop?",), "Yes, whenever you want.", "")


def write_knowledge(path, rows):
    book = openpyxl.Workbook()
    for row in rows:
        book.active.append(row)
    book.save(path)
    return path


def test_knowledge_reads_one_entry_per_row(tmp_path):
    path = write_knowledge(tmp_path / "knowledge.xlsx", [
        COLUMNS,
        ["info", "Information", "Where can I read more?", "Is there a website?\n\n  ", "On the study's website.", "https://example.org/info"],
        [None] * 6,  # an empty row is skipped
        ["stop", "Taking part", "Can I stop?", None, "Yes, whenever you want.", None],
    ])
    assert load_knowledge(path) == (INFO, STOP)


def test_without_knowledge_xlsx_no_questions_are_answered(tmp_path):
    assert load_knowledge(tmp_path / "knowledge.xlsx") is None


@pytest.mark.parametrize("rows, problem", [
    ([["id", "question", "answer"]], "lacks the column topic, phrasings, link"),
    ([COLUMNS, ["a", "", "Why?", "", "", ""]], "needs an id, a question and an answer"),
    ([COLUMNS, ["a", "", "Why?", "", "Because.", ""], ["a", "", "How?", "", "So.", ""]], "id may appear once"),
    ([COLUMNS, ["a", "", "Why?", "", "Because.", ""], ["b", "", "How?", "why?", "So.", ""]], "phrasing may appear once"),
])
def test_knowledge_mistakes_name_the_problem(tmp_path, rows, problem):
    with pytest.raises(ValueError, match=problem):
        load_knowledge(write_knowledge(tmp_path / "knowledge.xlsx", rows))


def test_answer_text_puts_the_link_on_its_own_line():
    assert matching.answer_text(INFO) == "On the study's website.\nhttps://example.org/info"
    assert matching.answer_text(STOP) == "Yes, whenever you want."


@pytest.fixture
def ask(client, db, settings, monkeypatch):
    """Post a question to /bridge/ask as Tilbot does; the intent service answers with the given phrasing."""
    settings.STUDY = dataclasses.replace(STUDY, knowledge=(INFO, STOP))
    settings.BRIDGE_SECRET = SECRET
    participant = Participant.objects.create(code="K7QM", age=50, gender="Other")

    def post(question, closest=None, secret=SECRET):
        monkeypatch.setattr(matching, "closest_phrasing", lambda q, phrasings, url: closest(phrasings) if callable(closest) else closest)
        return client.post("/bridge/ask", {"participant_id": make_token(participant.pk), "user_input": question, "bridge_secret": secret})
    return post


def test_ask_answers_with_the_matched_entry(ask):
    response = ask("is there a site with more?", closest="Is there a website?")
    assert response.json() == {"intent": "answered", "connector_label": "On the study's website.\nhttps://example.org/info"}
    assert Question.objects.get().entry == "info"


def test_ask_offers_every_question_and_phrasing(ask):
    seen = []
    ask("anything", closest=lambda phrasings: seen.extend(phrasings))
    assert seen == ["Where can I read more?", "Is there a website?", "Can I stop?"]


def test_ask_says_unknown_and_keeps_the_question(ask):
    assert ask("what is the weather?", closest=None).json() == {"intent": "unknown"}
    question = Question.objects.get()
    assert (question.text, question.entry) == ("what is the weather?", "")


def test_ask_keeps_no_question_text_without_transcripts(ask, settings):
    settings.STUDY = dataclasses.replace(settings.STUDY, transcripts=False)
    ask("Can I stop?", closest="Can I stop?")
    assert (Question.objects.get().text, Question.objects.get().entry) == ("", "stop")


def test_ask_refuses_a_wrong_secret_and_an_empty_question(ask):
    assert ask("anything", secret="wrong").status_code == 403
    assert ask("   ").status_code == 400
    assert not Question.objects.exists()


def test_ask_answers_503_when_the_intent_service_is_down(client, db, settings, monkeypatch):
    settings.STUDY = dataclasses.replace(STUDY, knowledge=(INFO,))
    settings.BRIDGE_SECRET = SECRET
    participant = Participant.objects.create(code="K7QM", age=50, gender="Other")

    def unreachable(question, phrasings, url):
        raise OSError("connection refused")
    monkeypatch.setattr(matching, "closest_phrasing", unreachable)
    response = client.post("/bridge/ask", {"participant_id": make_token(participant.pk), "user_input": "hi", "bridge_secret": SECRET})
    assert response.status_code == 503
    assert not Question.objects.exists()


def test_ask_is_not_found_without_a_knowledge_base(client, db, settings):
    settings.STUDY = STUDY
    settings.BRIDGE_SECRET = SECRET
    assert client.post("/bridge/ask", {"bridge_secret": SECRET}).status_code == 404


def test_ask_says_busy_after_too_many_questions_in_an_hour(ask, settings):
    from bridge.views import QUESTIONS_PER_HOUR
    participant = Participant.objects.get()
    Question.objects.bulk_create([Question(participant=participant, entry="") for _ in range(QUESTIONS_PER_HOUR)])
    assert ask("Can I stop?", closest="Can I stop?").json() == {"intent": "busy"}
    assert Question.objects.count() == QUESTIONS_PER_HOUR  # the refused question isn't kept

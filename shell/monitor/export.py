"""The study's data as CSV rows, decrypted, for analysis. Pure functions: the view writes the file.

With codes, a row can be traced to the person who shows that code; without, participants are numbered
1, 2, 3 … in order of sign-up, the same number in every file, so the files can be joined but not traced.
The scores are computed here from the answers, as the participant saw them; they are not stored.
Answers, transcripts and questions come session by session (by_session), the earliest first; the other files
are in order of time, or of sign-up.
"""

from django.conf import settings
from django.utils.timezone import localtime

from accounts.models import Participant
from phase2_feedback.scoring import scale_score, worth_discussing
from records.models import Answer, FeedbackShown, Narrative, Question, TranscriptLine, latest_answers


def participant_label(participant, with_codes: bool, numbers: dict[int, int]) -> str:
    return participant.code if with_codes else str(numbers[participant.pk])


def numbering() -> dict[int, int]:
    """Participant pk -> 1-based number in order of sign-up."""
    return {pk: number for number, pk in enumerate(Participant.objects.order_by("created", "pk").values_list("pk", flat=True), start=1)}


def by_session(records, session, within) -> list:
    """The records grouped per session (one conversation, or one participant's round): the session that started
    first at the top, and each session's records together, in their own order, even when sessions overlapped."""
    records = list(records)
    started = {}
    for r in records:
        key = session(r)
        started[key] = min(started.get(key, r.at), r.at)
    return sorted(records, key=lambda r: (started[session(r)], session(r), within(r)))


def participant_rows(with_codes: bool, numbers: dict[int, int]) -> list[list]:
    rows = [["participant", "age", "gender", "signed_up", "rounds", "condition", "character"]]
    for p in Participant.objects.order_by("created", "pk"):
        rows.append([participant_label(p, with_codes, numbers), p.age, p.gender, localtime(p.created).isoformat(), p.round, p.condition, p.character])
    return rows


def answer_rows(with_codes: bool, numbers: dict[int, int]) -> list[list]:
    rows = [["participant", "round", "item", "value", "at"]]
    answers = Answer.objects.select_related("participant")
    for a in by_session(answers, lambda a: (a.participant_id, a.round), lambda a: (a.at, a.pk)):
        rows.append([participant_label(a.participant, with_codes, numbers), a.round, a.item, a.value, localtime(a.at).isoformat()])
    return rows


def transcript_rows(with_codes: bool, numbers: dict[int, int]) -> list[list]:
    rows = [["participant", "conversation", "seq", "event", "text", "at"]]
    lines = TranscriptLine.objects.select_related("participant")
    for line in by_session(lines, lambda line: line.conversation, lambda line: line.seq):
        rows.append([participant_label(line.participant, with_codes, numbers), line.conversation, line.seq, line.event, line.text, localtime(line.at).isoformat()])
    return rows


def score_rows(with_codes: bool, numbers: dict[int, int]) -> list[list]:
    """One row per participant and scale of feedback.toml, with the latest answers; headers only without it."""
    rows = [["participant", "scale", "score", "worth_discussing"]]
    feedback = settings.STUDY.feedback
    scales = feedback.scales if feedback else ()
    for p in Participant.objects.order_by("created", "pk"):
        answers = latest_answers(p.pk)
        for scale in scales:
            score = scale_score(scale, settings.STUDY.items, answers)
            if score is not None:
                rows.append([participant_label(p, with_codes, numbers), scale.id, round(score, 1), worth_discussing(scale, score)])
    return rows


def question_rows(with_codes: bool, numbers: dict[int, int]) -> list[list]:
    """Phase 3: every question asked, and the knowledge base entry it was matched to (empty: none)."""
    rows = [["participant", "question", "entry", "at"]]
    questions = Question.objects.select_related("participant")
    for q in by_session(questions, lambda q: q.participant_id, lambda q: (q.at, q.pk)):
        rows.append([participant_label(q.participant, with_codes, numbers), q.text, q.entry, localtime(q.at).isoformat()])
    return rows


def feedback_rows(with_codes: bool, numbers: dict[int, int]) -> list[list]:
    """Phase 2: when each participant was shown their results, and how (panel, chat or both)."""
    rows = [["participant", "show", "at"]]
    for f in FeedbackShown.objects.select_related("participant").order_by("at", "pk"):
        rows.append([participant_label(f.participant, with_codes, numbers), f.show, localtime(f.at).isoformat()])
    return rows


def narrative_rows(with_codes: bool, numbers: dict[int, int]) -> list[list]:
    """Phase 2 with narrative.toml: the story each participant got after each round; generated False: the fallback."""
    rows = [["participant", "round", "character", "generated", "text", "at"]]
    for n in Narrative.objects.select_related("participant").order_by("at", "pk"):
        rows.append([participant_label(n.participant, with_codes, numbers), n.round, n.character, n.generated, n.text, localtime(n.at).isoformat()])
    return rows


def files_of(study) -> dict:
    """The files of this study's export: participants and answers always, every other file only when the study
    uses its part, so an empty file means no data yet, never a part the study doesn't have."""
    used = {
        "scores": study.feedback is not None,
        "feedback": study.feedback is not None,
        "narratives": study.narrative is not None,
        "questions": study.knowledge is not None,
        "transcripts": study.transcripts,
    }
    return {name: rows for name, rows in FILES.items() if used.get(name, True)}


FILES = {
    "participants": participant_rows,
    "answers": answer_rows,
    "scores": score_rows,
    "feedback": feedback_rows,
    "narratives": narrative_rows,
    "questions": question_rows,
    "transcripts": transcript_rows,
}

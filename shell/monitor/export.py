"""The study's data as CSV rows, decrypted, for analysis. Pure functions: the view writes the file.

With codes, a row can be traced to the person who shows that code; without, participants are numbered
1, 2, 3 … in order of sign-up, the same number in every file, so the files can be joined but not traced.
The scores are computed here from the answers, as the participant saw them; they are not stored.
"""

from django.conf import settings
from django.utils.timezone import localtime

from accounts.models import Participant
from phase2_feedback.scoring import scale_score, worth_discussing
from records.models import Answer, TranscriptLine, latest_answers


def participant_label(participant, with_codes: bool, numbers: dict[int, int]) -> str:
    return participant.code if with_codes else str(numbers[participant.pk])


def numbering() -> dict[int, int]:
    """Participant pk -> 1-based number in order of sign-up."""
    return {pk: number for number, pk in enumerate(Participant.objects.order_by("created", "pk").values_list("pk", flat=True), start=1)}


def participant_rows(with_codes: bool, numbers: dict[int, int]) -> list[list]:
    rows = [["participant", "age", "gender", "signed_up"]]
    for p in Participant.objects.order_by("created", "pk"):
        rows.append([participant_label(p, with_codes, numbers), p.age, p.gender, localtime(p.created).isoformat()])
    return rows


def answer_rows(with_codes: bool, numbers: dict[int, int]) -> list[list]:
    rows = [["participant", "item", "value", "at"]]
    for a in Answer.objects.select_related("participant").order_by("at", "pk"):
        rows.append([participant_label(a.participant, with_codes, numbers), a.item, a.value, localtime(a.at).isoformat()])
    return rows


def transcript_rows(with_codes: bool, numbers: dict[int, int]) -> list[list]:
    rows = [["participant", "conversation", "seq", "event", "text", "at"]]
    for line in TranscriptLine.objects.select_related("participant").order_by("conversation", "seq"):
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


FILES = {
    "participants": participant_rows,
    "answers": answer_rows,
    "scores": score_rows,
    "transcripts": transcript_rows,
}

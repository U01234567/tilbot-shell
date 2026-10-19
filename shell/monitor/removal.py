"""Deleting participant data: one participant on request (the researcher dashboard), or everyone at the
end of a study (python start_shell.py erase). Deleting is never automatic: it is a researcher's decision.
"""

from django.contrib.sessions.models import Session
from django.db import transaction

from accounts.models import Attempt, Participant
from accounts.session import SESSION_KEY
from records.models import Answer, Question, TranscriptLine

# Everything stored per participant, in the order it must go: the participant itself is protected
# (on_delete=PROTECT) as long as any of these still points to it.
PER_PARTICIPANT = {"answers": Answer, "questions": Question, "transcript lines": TranscriptLine}


def stored_for(participant: Participant) -> dict[str, int]:
    """What would be deleted with this participant, counted."""
    return {name: model.objects.filter(participant=participant).count() for name, model in PER_PARTICIPANT.items()}


@transaction.atomic
def remove(participant: Participant) -> None:
    """Delete one participant, everything stored for them, and their sign-in sessions."""
    for model in PER_PARTICIPANT.values():
        model.objects.filter(participant=participant).delete()
    for session in Session.objects.all():  # sessions are encoded, so each one is opened to check
        if session.get_decoded().get(SESSION_KEY) == participant.pk:
            session.delete()
    participant.delete()


@transaction.atomic
def erase_all() -> None:
    """Delete every participant and everything stored for them, the sign-in attempts and all sessions.

    Researcher accounts and Tilbot's projects stay. Backups made before still hold the data.
    """
    for model in PER_PARTICIPANT.values():
        model.objects.all().delete()
    Participant.objects.all().delete()
    Attempt.objects.all().delete()
    Session.objects.all().delete()

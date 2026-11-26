from django.db import models

from accounts.models import Participant
from records.fields import EncryptedTextField


class Answer(models.Model):
    """One answer to one questionnaire item (phase 1), stored as text, for example "7"."""

    participant = models.ForeignKey("accounts.Participant", on_delete=models.PROTECT, related_name="answers")
    item = models.CharField(max_length=20)
    value = EncryptedTextField()
    at = models.DateTimeField(auto_now_add=True)
    round = models.PositiveIntegerField(default=1)  # the participant's round when they answered


class TranscriptLine(models.Model):
    """One conversation event from Tilbot, sent by its ShellLogger (patch 0002)."""

    participant = models.ForeignKey(
        "accounts.Participant", on_delete=models.PROTECT, related_name="transcript"
    )
    conversation = models.CharField(max_length=36)  # one id per Tilbot conversation
    seq = models.PositiveIntegerField()  # order within the conversation
    event = models.CharField(max_length=40)  # message_bot, message_user, session_end, ...
    text = EncryptedTextField(blank=True)
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["conversation", "seq"]


class Question(models.Model):
    """One question a participant typed (phase 3), and the knowledge base entry it was matched to."""

    participant = models.ForeignKey("accounts.Participant", on_delete=models.PROTECT, related_name="questions")
    text = EncryptedTextField(blank=True)  # empty when the study keeps no transcripts: free text can say anything
    entry = models.CharField(max_length=100, blank=True)  # the entry's id in knowledge.xlsx; empty: no match
    at = models.DateTimeField(auto_now_add=True)


class FeedbackShown(models.Model):
    """The results were shown to a participant at the end of the questionnaire, and how (feedback.toml's show)."""

    participant = models.ForeignKey("accounts.Participant", on_delete=models.PROTECT, related_name="feedback_shown")
    show = models.CharField(max_length=10)  # panel, chat or both
    at = models.DateTimeField(auto_now_add=True)


class Narrative(models.Model):
    """The story a participant got after one round, written by a language model (narrative.toml)."""

    participant = models.ForeignKey("accounts.Participant", on_delete=models.PROTECT, related_name="narratives")
    round = models.PositiveIntegerField()
    character = models.CharField(max_length=40)
    text = EncryptedTextField()
    generated = models.BooleanField()  # False: the model failed, and the participant got narrative.toml's fallback
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["participant", "round"], name="one_narrative_per_round")]


def latest_answers(participant_id: int) -> dict[str, int]:
    """Item id -> the participant's answer to it in their current round; when an item was answered twice, the
    latest counts. Without questionnaire.toml's repeat, every answer is in round 1."""
    current = Participant.objects.values_list("round", flat=True).get(pk=participant_id)
    answers = Answer.objects.filter(participant_id=participant_id, round=current).order_by("at", "pk")
    return {answer.item: int(answer.value) for answer in answers}

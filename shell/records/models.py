from django.db import models

from records.fields import EncryptedTextField


class Answer(models.Model):
    """One answer to one questionnaire item (phase 1), stored as text, for example "7"."""

    participant = models.ForeignKey("accounts.Participant", on_delete=models.PROTECT, related_name="answers")
    item = models.CharField(max_length=20)
    value = EncryptedTextField()
    at = models.DateTimeField(auto_now_add=True)


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


def latest_answers(participant_id: int) -> dict[str, int]:
    """Item id -> the participant's answer to it; when an item was answered twice, the latest counts."""
    answers = Answer.objects.filter(participant_id=participant_id).order_by("at", "pk")
    return {answer.item: int(answer.value) for answer in answers}

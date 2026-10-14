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

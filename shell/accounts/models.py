"""Who the participants are: a code, an age and a gender, nothing more (see ETHICS.md). With sign-in by link the
code is the ID in the link, and there is no age or gender."""

from django.db import models

class Participant(models.Model):
    code = models.CharField(max_length=64, unique=True)  # 4 characters (codes.py), or the ID in the link
    age = models.PositiveSmallIntegerField(null=True)
    gender = models.CharField(max_length=40, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    round = models.PositiveIntegerField(default=1)  # questionnaire.toml's repeat: every sign-in starts the next one
    condition = models.CharField(max_length=40, blank=True)  # narrative.toml: drawn once, at sign-up
    character = models.CharField(max_length=40, blank=True)  # the story's main character, for a "fixed" condition


class Attempt(models.Model):
    """A sign-up or a failed sign-in, counted per IP address to slow down guessing."""

    class Kind(models.TextChoices):
        SIGN_UP = "sign_up"
        FAILED_SIGN_IN = "failed_sign_in"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    ip = models.GenericIPAddressField()
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["kind", "ip", "at"])]


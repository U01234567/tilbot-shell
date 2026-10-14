"""Who the participants are: a code, an age and a gender, nothing more (see ETHICS.md)."""

from django.db import models

from accounts.codes import LENGTH


class Participant(models.Model):
    code = models.CharField(max_length=LENGTH, unique=True)
    age = models.PositiveSmallIntegerField()
    gender = models.CharField(max_length=40)
    created = models.DateTimeField(auto_now_add=True)


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


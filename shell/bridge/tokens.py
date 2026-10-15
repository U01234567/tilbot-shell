"""Tokens that tell the shell which participant Tilbot is talking to.

The chat page gives Tilbot a signed token, never the participant's code, so nobody can type
someone else's code into the URL. Signed with Django's own signing, no home-made cryptography.
"""

from django.conf import settings
from django.core import signing

SALT = "bridge.participant"


def make_token(participant_id: int) -> str:
    return signing.dumps(participant_id, salt=SALT)


def read_token(token: str) -> int:
    """Return the participant id; raise signing.BadSignature for a forged or expired token."""
    return signing.loads(token, salt=SALT, max_age=settings.SESSION_COOKIE_AGE)

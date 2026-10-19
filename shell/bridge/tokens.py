"""Tokens that tell the shell which participant Tilbot is talking to.

The chat page gives Tilbot a token, never the participant's code, so nobody can type someone else's
code into the address. The token is encrypted, not only signed: whoever reads the chat's address can't
see the participant's row number in it, so not how many people signed up before them. Fernet from the
cryptography package, with its own key derived from SECRET_KEY: no home-made cryptography.
"""

import base64
from functools import cache

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.core import signing

PURPOSE = b"bridge.participant"  # a key for this use only, apart from every other use of SECRET_KEY


@cache
def fernet() -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=PURPOSE).derive(settings.SECRET_KEY.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def make_token(participant_id: int) -> str:
    return fernet().encrypt(str(participant_id).encode()).decode()


def read_token(token: str) -> int:
    """Return the participant id; raise signing.BadSignature for a forged, damaged or expired token."""
    try:
        return int(fernet().decrypt(token.encode(), ttl=settings.SESSION_COOKIE_AGE))
    except (InvalidToken, ValueError) as error:
        raise signing.BadSignature("forged, damaged or expired token") from error

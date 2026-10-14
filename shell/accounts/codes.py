"""Participant codes: four random characters, easy to read aloud and to type."""

import secrets

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford's base32: no I, L, O or U
LENGTH = 4  # 32 ** 4 = 1,048,576 possible codes
LOOKALIKES = str.maketrans("OIL", "011")  # letters people type when they mean 0 or 1


def new_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))


def normalize(typed: str) -> str:
    """Return a typed code in its stored form: no spaces, upper case, look-alikes replaced."""
    return typed.strip().upper().translate(LOOKALIKES)

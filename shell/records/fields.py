"""A text field that is encrypted before it reaches the database.

Fernet, from the cryptography package, encrypts and authenticates every value.
Encrypted columns cannot be searched, sorted or compared in SQL: filter on the other columns.
Losing FIELD_ENCRYPTION_KEY makes every value unreadable (docs/operations.md).
"""

from functools import cache

from cryptography.fernet import Fernet
from django.conf import settings
from django.db import models


@cache
def fernet() -> Fernet:
    return Fernet(settings.FIELD_ENCRYPTION_KEY)


class EncryptedTextField(models.TextField):
    def get_prep_value(self, value):
        return fernet().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        return fernet().decrypt(value.encode()).decode()

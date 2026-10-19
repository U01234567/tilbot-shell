"""python manage.py backup_cipher encrypt|decrypt: bytes in on stdin, bytes out on stdout.

start_shell.py backup and restore send every backup file through this, so a backup is encrypted with
FIELD_ENCRYPTION_KEY before it leaves the containers, and only this key can open it again. The data
passes in memory, as bytes: it never lands on disk unencrypted and no terminal can change it.
"""

import sys

from cryptography.fernet import InvalidToken
from django.core.management.base import BaseCommand, CommandError

from records.fields import fernet


class Command(BaseCommand):
    help = "Encrypt or decrypt stdin to stdout with FIELD_ENCRYPTION_KEY."

    def add_arguments(self, parser):
        parser.add_argument("direction", choices=["encrypt", "decrypt"])

    def handle(self, direction, **options):
        data = sys.stdin.buffer.read()
        try:
            result = fernet().encrypt(data) if direction == "encrypt" else fernet().decrypt(data)
        except InvalidToken:
            raise CommandError("this backup was not made with the FIELD_ENCRYPTION_KEY in .env, or it is damaged")
        sys.stdout.buffer.write(result)

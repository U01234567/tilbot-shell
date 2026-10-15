"""python start_shell.py researcher: one name and password for both dashboards.

Makes a researcher account here (or sets a new password for an existing one), and a Tilbot account with
the same name and password, through Tilbot's own "create user" call, logged in as Tilbot's admin with
TILBOT_ADMIN_PASSWORD from .env. Nobody ever needs to log in as that admin.
"""

import getpass
import os
from http.cookiejar import CookieJar
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, build_opener

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

TILBOT_API = "http://tilbot-backend:8000/api/"
TILBOT_ACCEPTS = ("OK", "USER_EXISTS")  # Tilbot answers with a short text (backend/errors.ts)


def tilbot_call(opener, path: str, form: dict | None = None) -> str:
    data = urlencode(form).encode() if form is not None else None
    with opener.open(TILBOT_API + path, data=data, timeout=10) as response:
        return response.read().decode()


def make_tilbot_account(name: str, password: str) -> str:
    """Return Tilbot's answer: "OK", "USER_EXISTS", or another code when it refused."""
    opener = build_opener(HTTPCookieProcessor(CookieJar()))  # keeps the admin's session cookie
    tilbot_call(opener, "admin_account_exists")  # creates Tilbot's admin on first use, as its login page does
    admin = {"username": "admin", "password": os.environ["TILBOT_ADMIN_PASSWORD"]}
    if tilbot_call(opener, "login", admin) != "OK":
        raise CommandError(
            "Tilbot refused its admin password: was it changed in Tilbot's dashboard? "
            "Then make the Tilbot account by hand there, as admin."
        )
    return tilbot_call(opener, "create_user_account", {"username": name, "password": password})


def add_researcher(name: str, password: str, tilbot_account=make_tilbot_account) -> str:
    """Make or reset the researcher account, after Tilbot accepted the name; return Tilbot's answer."""
    if not name:
        raise CommandError("Give a name.")
    user = User.objects.filter(username=name).first() or User(username=name)
    try:
        validate_password(password, user)
    except ValidationError as error:
        raise CommandError(" ".join(error.messages)) from error
    answer = tilbot_account(name, password)
    if answer not in TILBOT_ACCEPTS:
        raise CommandError(f"Tilbot refused the account ({answer}); nothing was changed.")
    user.set_password(password)
    user.save()
    return answer


class Command(BaseCommand):
    help = "Make a researcher account here and in Tilbot, with one name and password."

    def handle(self, *args, **options):
        name = input("Name: ").strip()
        password = getpass.getpass("Password, 12 characters or more: ")
        if password != getpass.getpass("Password again: "):
            raise CommandError("The two passwords differ; nothing was changed.")
        try:
            answer = add_researcher(name, password)
        except URLError as error:
            raise CommandError(f"Tilbot can't be reached ({error.reason}): is everything running?") from error
        self.stdout.write(f"Ready. Log in with {name} on both dashboards: http://127.0.0.1:8081/researcher/")
        if answer == "USER_EXISTS":
            self.stdout.write(f"Tilbot already had an account {name}: its password there stays as it was.")

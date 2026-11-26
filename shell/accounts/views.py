"""Sign up, sign in and sign out, or sign in by the ID in the link (project.toml's [signup] by_link).

Messages stay vague on purpose: a wrong code never reveals whether a code exists.
Every text comes from the study's project.toml, so each study chooses its own language.
Both sign-ups and failed sign-ins are limited per IP address to slow down guessing.
"""

import re
import secrets
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import SignInForm, SignUpForm
from accounts.codes import new_code
from accounts.models import Attempt, Participant
from accounts.session import sign_in_as

WINDOW = timedelta(minutes=15)
FAILED_SIGN_INS_ALLOWED = 5  # per IP address per window
SIGN_UPS_ALLOWED = 10  # per IP address per window
LINK_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")  # an ID in the link: letters, digits, - and _


def home(request):
    """The start page; with sign-in by link, https://SHELL_HOST/?id=<ID> signs in, and a new ID is a new participant."""
    if not settings.STUDY.by_link:
        return render(request, "accounts/home.html")
    code = request.GET.get("id", "")
    if not LINK_ID.fullmatch(code):
        return render(request, "accounts/link.html")
    participant = Participant.objects.filter(code=code).first()
    if participant is None:
        ip = client_ip(request)
        if is_blocked(ip, Attempt.Kind.SIGN_UP, SIGN_UPS_ALLOWED):
            return render(request, "accounts/blocked.html", status=429)
        record_attempt(Attempt.Kind.SIGN_UP, ip)
        participant = Participant.objects.create(code=code, **assigned())
    else:
        start_round(participant)
    sign_in_as(request, participant)
    return redirect("chat")


def assigned() -> dict[str, str]:
    """A new participant's condition in narrative.toml: the one with the fewest participants, drawn at random when
    several have as few. A "fixed" condition also draws the story's main character, kept from then on."""
    narrative = settings.STUDY.narrative
    if narrative is None:
        return {}
    counts = Counter(Participant.objects.values_list("condition", flat=True))
    fewest = min(counts[c.id] for c in narrative.conditions)
    condition = secrets.choice([c for c in narrative.conditions if counts[c.id] == fewest])
    return {"condition": condition.id, "character": secrets.choice(narrative.names) if condition.name == "fixed" else ""}


def start_round(participant) -> None:
    """With questionnaire.toml's repeat, every sign-in starts a new round of the same questions."""
    if settings.STUDY.repeat:
        participant.round += 1
        participant.save(update_fields=["round"])


def sign_up(request):
    if settings.STUDY.by_link:
        return redirect("home")
    ip = client_ip(request)
    if is_blocked(ip, Attempt.Kind.SIGN_UP, SIGN_UPS_ALLOWED):
        return render(request, "accounts/blocked.html", status=429)
    form = SignUpForm(request.POST or None)
    code = request.session.get("new_code")
    if request.method != "POST" or code is None or not form.is_valid():
        return show_sign_up(request, form)

    record_attempt(Attempt.Kind.SIGN_UP, ip)
    del request.session["new_code"]
    try:
        participant = Participant.objects.create(code=code, **form.cleaned_data, **assigned())
    except IntegrityError:  # someone else got the same random code first: about 1 in a million
        return show_sign_up(request, form, notice=settings.STUDY.texts["id_taken"])
    sign_in_as(request, participant)
    return redirect("chat")


def show_sign_up(request, form, notice=""):
    """Show the form with the code this browser will get, chosen once and kept in the session.

    The session, not a hidden form field, holds the code: nobody can pick their own.
    """
    if "new_code" not in request.session:
        request.session["new_code"] = new_code()
    context = {"form": form, "code": request.session["new_code"], "notice": notice}
    return render(request, "accounts/sign_up.html", context)


def sign_in(request):
    if settings.STUDY.by_link:
        return redirect("home")
    ip = client_ip(request)
    if is_blocked(ip, Attempt.Kind.FAILED_SIGN_IN, FAILED_SIGN_INS_ALLOWED):
        return render(request, "accounts/blocked.html", status=429)
    form = SignInForm(request.POST or None)
    if request.method != "POST" or not form.is_valid():
        return render(request, "accounts/sign_in.html", {"form": form})

    participant = Participant.objects.filter(code=form.cleaned_data["code"]).first()
    if participant is None:
        record_attempt(Attempt.Kind.FAILED_SIGN_IN, ip)
        form.add_error("code", settings.STUDY.texts["wrong_id"])
        return render(request, "accounts/sign_in.html", {"form": form})
    start_round(participant)
    sign_in_as(request, participant)
    return redirect("chat")


@require_POST
def sign_out(request):
    request.session.flush()
    return redirect("home")


def client_ip(request) -> str:
    # Caddy replaces X-Forwarded-For with the address it saw, so the header can be trusted here.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[-1].strip() or request.META["REMOTE_ADDR"]


def is_blocked(ip: str, kind: str, allowed: int) -> bool:
    since = timezone.now() - WINDOW
    return Attempt.objects.filter(kind=kind, ip=ip, at__gte=since).count() >= allowed


def record_attempt(kind: str, ip: str) -> None:
    """Store the attempt and forget every attempt older than the window: IP addresses are kept for minutes, not months."""
    Attempt.objects.filter(at__lt=timezone.now() - WINDOW).delete()
    Attempt.objects.create(kind=kind, ip=ip)

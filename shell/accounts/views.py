"""Sign up, sign in and sign out.

Messages stay vague on purpose: a wrong code never reveals whether a code exists.
Every text comes from the study's project.toml, so each study chooses its own language.
Both sign-ups and failed sign-ins are limited per IP address to slow down guessing.
"""

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


def home(request):
    return render(request, "accounts/home.html")


def sign_up(request):
    ip = client_ip(request)
    if is_blocked(ip, Attempt.Kind.SIGN_UP, SIGN_UPS_ALLOWED):
        return render(request, "accounts/blocked.html", status=429)
    form = SignUpForm(request.POST or None)
    code = request.session.get("new_code")
    if request.method != "POST" or code is None or not form.is_valid():
        return show_sign_up(request, form)

    Attempt.objects.create(kind=Attempt.Kind.SIGN_UP, ip=ip)
    del request.session["new_code"]
    try:
        participant = Participant.objects.create(code=code, **form.cleaned_data)
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
    ip = client_ip(request)
    if is_blocked(ip, Attempt.Kind.FAILED_SIGN_IN, FAILED_SIGN_INS_ALLOWED):
        return render(request, "accounts/blocked.html", status=429)
    form = SignInForm(request.POST or None)
    if request.method != "POST" or not form.is_valid():
        return render(request, "accounts/sign_in.html", {"form": form})

    participant = Participant.objects.filter(code=form.cleaned_data["code"]).first()
    if participant is None:
        Attempt.objects.create(kind=Attempt.Kind.FAILED_SIGN_IN, ip=ip)
        form.add_error("code", settings.STUDY.texts["wrong_id"])
        return render(request, "accounts/sign_in.html", {"form": form})
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

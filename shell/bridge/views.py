from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.session import signed_in_id
from bridge.tokens import make_token, read_token
from records.models import Answer, TranscriptLine
from phase1_collect.rules import parse_answer, route_after


def chat(request):
    participant_id = signed_in_id(request)
    if participant_id is None:
        return redirect("home")
    query = urlencode({
        "project": settings.STUDY.tilbot_project_id,
        "pid": make_token(participant_id),
        "show_header": 0,
    })
    return render(request, "bridge/chat.html", {"bot_url": f"{settings.BOT_URL}/?{query}"})


@csrf_exempt  # called by Tilbot's server, not a browser; BRIDGE_SECRET and the token protect it
@require_POST
def save(request):
    """Store one phase-1 answer, then tell Tilbot which connector to follow.

    Replies only after the answer is committed. Any error returns 4xx, which makes Tilbot follow
    the block's "else" connector: "something went wrong, we ask again". No answer is lost silently.
    """
    if not has_secret(request):
        return HttpResponseForbidden()
    try:
        participant_id = read_token(request.POST["participant_id"])
        item = settings.STUDY.items[request.POST["item"]]
        value = parse_answer(item, request.POST["user_input"])
    except (KeyError, ValueError, signing.BadSignature) as error:
        return HttpResponseBadRequest(repr(error))
    Answer.objects.create(participant_id=participant_id, item=item.id, value=value)
    return JsonResponse({"intent": route_after(item, value)})


@csrf_exempt  # called by Tilbot's server, not a browser; BRIDGE_SECRET and the token protect it
@require_POST
def log(request):
    """Store one conversation event from Tilbot's ShellLogger (patch 0002)."""
    if not has_secret(request):
        return HttpResponseForbidden()
    try:
        TranscriptLine.objects.create(
            participant_id=read_token(request.POST["participant_id"]),
            conversation=request.POST["conversation"],
            seq=int(request.POST["seq"]),
            event=request.POST["event"],
            text=request.POST.get("detail", ""),
        )
    except (KeyError, ValueError, signing.BadSignature) as error:
        return HttpResponseBadRequest(repr(error))
    return HttpResponse(status=204)


def has_secret(request) -> bool:
    return constant_time_compare(request.POST.get("bridge_secret", ""), settings.BRIDGE_SECRET)

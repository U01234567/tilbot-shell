from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.session import signed_in_id
from config.project import NO_TILBOT_PROJECT
from bridge.tokens import make_token, read_token
from records.models import Answer, FeedbackShown, Question, TranscriptLine, latest_answers
from phase1_collect.rules import parse_answer, questionnaire_done, route_after
from phase2_feedback.story import chart, story
from phase3_questions import matching

RETURNING = "returning"  # Tilbot connector at the start: every item is answered, skip the questions
NEW = "new"  # Tilbot connector at the start: the questionnaire comes first

ANSWERED = "answered"  # Tilbot connector: show the answer, which comes as the connector's label
UNKNOWN = "unknown"  # Tilbot connector: the knowledge base has no answer
BUSY = "busy"  # Tilbot connector: this participant asked QUESTIONS_PER_HOUR questions in the last hour
QUESTIONS_PER_HOUR = 30  # so one participant can't keep the matching service busy for everyone else

PANEL = "panel"  # Tilbot connector after part=story: open the panel (the event show_results), no story
CHAT = "chat"  # Tilbot connector: show the text, which comes as the connector's label


def chat(request):
    participant_id = signed_in_id(request)
    if participant_id is None:
        return redirect("home")
    if settings.STUDY.tilbot_project_id == NO_TILBOT_PROJECT:
        return render(request, "bridge/chat.html", {"bot_url": None})
    query = urlencode({"project": settings.STUDY.tilbot_project_id, "pid": make_token(participant_id)})
    done = questionnaire_done(settings.STUDY.items, latest_answers(participant_id))
    return render(request, "bridge/chat.html", {
        "bot_url": f"{settings.BOT_URL}/?{query}",
        "bot_origin": settings.BOT_URL,
        "done": done,  # every item answered: leaving needs no warning
    })


@csrf_exempt  # called by Tilbot's server, not a browser; BRIDGE_SECRET and the token protect it
@require_POST
def status(request):
    """At the start of every chat: tell Tilbot whether this participant answered every item already."""
    if not has_secret(request):
        return HttpResponseForbidden()
    try:
        participant_id = read_token(request.POST["participant_id"])
    except (KeyError, signing.BadSignature) as error:
        return HttpResponseBadRequest(repr(error))
    done = questionnaire_done(settings.STUDY.items, latest_answers(participant_id))
    return JsonResponse({"intent": RETURNING if done else NEW})


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
    if not settings.STUDY.transcripts:
        return HttpResponse(status=204)
    try:
        TranscriptLine.objects.create(
            participant_id=read_token(request.POST["participant_id"]),
            conversation=request.POST["conversation"],
            seq=parse_seq(request.POST["seq"]),
            event=request.POST["event"],
            text=request.POST.get("detail", ""),
        )
    except (KeyError, ValueError, signing.BadSignature) as error:
        return HttpResponseBadRequest(repr(error))
    return HttpResponse(status=204)


def parse_seq(raw: str) -> int:
    """Return the line number, or raise ValueError below zero, so a bad one is a 400, not a 500."""
    seq = int(raw)
    if seq < 0:
        raise ValueError(f"seq {seq} is negative")
    return seq


@csrf_exempt  # called by Tilbot's server, not a browser; BRIDGE_SECRET and the token protect it
@require_POST
def feedback(request):
    """The results at the end of the questionnaire, as feedback.toml's show says (phase 2).

    Tilbot calls this with part=story: the shell notes that the results were shown and how, and replies
    "panel" (open the panel) or "chat" with the story as the connector's label. For the chat, Tilbot then calls
    with part=chart and gets the chart, with the connector "chat", or "both" to open the panel as well.
    Any error returns 4xx, which makes Tilbot follow "else".
    """
    study = settings.STUDY
    if not has_secret(request):
        return HttpResponseForbidden()
    if study.feedback is None:
        return HttpResponseNotFound("this study has no project/feedback.toml")
    try:
        participant_id = read_token(request.POST["participant_id"])
        part = request.POST["part"]
    except (KeyError, signing.BadSignature) as error:
        return HttpResponseBadRequest(repr(error))
    answers = latest_answers(participant_id)
    if not questionnaire_done(study.items, answers):
        return HttpResponseBadRequest("not every item is answered yet")
    show = study.feedback.show
    if part == "story":
        FeedbackShown.objects.create(participant_id=participant_id, show=show)
        if show == PANEL:
            return JsonResponse({"intent": PANEL})
        return JsonResponse({"intent": CHAT, "connector_label": story(study.feedback, study.items, answers)})
    if part == "chart":
        return JsonResponse({"intent": show, "connector_label": chart(study.feedback, study.items, answers)})
    return HttpResponseBadRequest(f"part must be story or chart, not {part!r}")


def has_secret(request) -> bool:
    return constant_time_compare(request.POST.get("bridge_secret", ""), settings.BRIDGE_SECRET)


@csrf_exempt  # called by Tilbot's server, not a browser; BRIDGE_SECRET and the token protect it
@require_POST
def ask(request):
    """Answer one question from the knowledge base (phase 3), and keep what was asked.

    Tilbot follows the connector "answered" and shows the answer text it gets as the connector's
    label, or follows "unknown", or "busy" after too many questions. Any error returns 4xx or 503, which makes
    Tilbot follow "else".
    """
    knowledge = settings.STUDY.knowledge
    if not has_secret(request):
        return HttpResponseForbidden()
    if knowledge is None:
        return HttpResponseNotFound("this study has no project/knowledge.xlsx")
    try:
        participant_id = read_token(request.POST["participant_id"])
        question = request.POST["user_input"].strip()
    except (KeyError, signing.BadSignature) as error:
        return HttpResponseBadRequest(repr(error))
    if not question:
        return HttpResponseBadRequest("the question is empty")
    hour_ago = timezone.now() - timedelta(hours=1)
    if Question.objects.filter(participant_id=participant_id, at__gte=hour_ago).count() >= QUESTIONS_PER_HOUR:
        return JsonResponse({"intent": BUSY})
    entries = matching.by_phrasing(knowledge)
    try:
        phrasing = matching.closest_phrasing(question, list(entries), settings.INTENT_URL)
    except (OSError, ValueError) as error:
        return HttpResponse(f"vector-similarity-intent: {error!r}", status=503)
    entry = entries.get(phrasing)
    Question.objects.create(
        participant_id=participant_id,
        text=question if settings.STUDY.transcripts else "",
        entry=entry.id if entry else "",
    )
    if entry is None:
        return JsonResponse({"intent": UNKNOWN})
    return JsonResponse({"intent": ANSWERED, "connector_label": matching.answer_text(entry)})

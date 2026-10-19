from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from accounts.session import signed_in_id
from phase2_feedback.scoring import scale_score, worth_discussing
from records.models import latest_answers


def results(request):
    """The participant's results, as the HTML of the panel beside the chat (static/js/chat.js puts it there)."""
    participant_id = signed_in_id(request)
    feedback = settings.STUDY.feedback
    if participant_id is None or feedback is None:
        raise Http404
    answers = latest_answers(participant_id)
    bars = []
    for scale in feedback.scales:
        score = scale_score(scale, settings.STUDY.items, answers)
        if score is not None:  # a scale with too few answers is left out
            bars.append(bar(scale, score))
    return render(request, "phase2_feedback/results.html", {
        "texts": feedback.texts,
        "better": [b for b in bars if b["scale"].higher == "better"],
        "worse": [b for b in bars if b["scale"].higher == "worse"],
    })


def bar(scale, score: float) -> dict:
    """What the template needs to draw one scale: its score, and the part of the bar that is worth discussing."""
    zone = None
    if scale.threshold is not None:
        zone = (0, scale.threshold) if scale.higher == "better" else (scale.threshold, 100 - scale.threshold)
    return {
        "scale": scale,
        "score": score,
        "flag": worth_discussing(scale, score),
        "zone": zone,  # (where it starts, how wide), on the bar's 0–100
    }

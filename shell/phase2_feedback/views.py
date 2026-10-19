from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from accounts.session import signed_in_id
from phase1_collect.rules import questionnaire_done
from phase2_feedback.scoring import scale_score, worth_discussing
from records.models import latest_answers


def results(request):
    """The participant's results, as the HTML of the panel beside the chat (static/js/chat.js puts it there).

    Only once every item is answered; before that, the panel says so.
    """
    participant_id = signed_in_id(request)
    feedback = settings.STUDY.feedback
    if participant_id is None or feedback is None:
        raise Http404
    answers = latest_answers(participant_id)
    bars = []
    if questionnaire_done(settings.STUDY.items, answers):
        for scale in feedback.scales:
            score = scale_score(scale, settings.STUDY.items, answers)
            if score is not None:  # a scale with too few answers is left out
                bars.append(bar(scale, score))
    return render(request, "phase2_feedback/results.html", {"texts": feedback.texts, "bars": bars})


def bar(scale, score: float) -> dict:
    """What the template needs to draw one scale on a 0–100 track: the score, whether it is worth
    discussing, and the two parts of the track, each as (where it starts, how wide)."""
    drawing = {"scale": scale, "score": score, "flag": worth_discussing(scale, score)}
    if scale.threshold is None:
        return drawing
    below, above = (0, scale.threshold), (scale.threshold, 100 - scale.threshold)
    worth, fine = (below, above) if scale.higher == "better" else (above, below)
    return {**drawing, "worth_zone": worth, "fine_zone": fine}

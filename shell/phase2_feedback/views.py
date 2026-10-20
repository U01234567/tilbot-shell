from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from accounts.session import signed_in_id
from phase1_collect.rules import questionnaire_done
from phase2_feedback.scoring import better_is_right, scored, worth_discussing
from records.models import latest_answers


def results(request):
    """The participant's results, as the HTML of the panel beside the chat (static/js/chat.js puts it there).

    Only once every item is answered; before that, the panel says so.
    """
    participant_id = signed_in_id(request)
    feedback = settings.STUDY.feedback
    if participant_id is None or feedback is None:
        raise Http404
    items = settings.STUDY.items
    answers = latest_answers(participant_id)
    shown = scored(feedback, items, answers) if questionnaire_done(items, answers) else []
    bars = [bar(scale, score, given(scale, items, answers)) for scale, score in shown]
    return render(request, "phase2_feedback/results.html", {"texts": feedback.texts, "bars": bars})


def given(scale, items, answers) -> list[tuple[str, str]]:
    """The questions a scale is based on, each with the participant's answer in the words of its button."""
    return [(items[i].text or i, items[i].answer_word(answers[i])) for i in scale.items if i in answers]


def bar(scale, score: float, answers: list[tuple[str, str]]) -> dict:
    """What the template needs to draw one scale: a line from worse (left, 0) to better (right, 100), whatever
    the scale's own direction, with a dot at the participant's place and, when the scale has a threshold, the
    place of the threshold on it. Plus whether the score is worth discussing, and the answers behind it."""
    drawing = {"scale": scale, "flag": worth_discussing(scale, score), "answers": answers, "at": better_is_right(scale, score)}
    if scale.threshold is None:
        return drawing
    return {**drawing, "limit": better_is_right(scale, scale.threshold)}


"""The story after each round (narrative.toml), written by a language model.

The shell fills the study's prompt with the main character's name, this round's answers and, for a condition with
memory = "all", the story so far, and asks the model. The study's guardrails are in its prompt; here the model gets a
time limit and a word limit, and when it fails the participant reads the study's fallback instead. Every story is
stored, encrypted, so the team can read what each participant was told.
"""

import json
import logging
import urllib.request

from django.conf import settings

from config.project import Narrative as Settings
from records.models import Narrative

logger = logging.getLogger(__name__)


def tell(participant, answers: dict[str, int]) -> Narrative:
    """Write, store and return the story of the participant's current round."""
    study = settings.STUDY
    narrative = study.narrative
    # A participant who signed up before narrative.toml existed has no condition: they get the first.
    condition = next((c for c in narrative.conditions if c.id == participant.condition), narrative.conditions[0])
    if condition.name == "fixed":
        name = participant.character
    else:  # "cycle": round 1 gets the first name, round 2 the second, and after the last the first again
        name = narrative.names[(participant.round - 1) % len(narrative.names)]
    so_far = ""
    if condition.memory == "all":
        told = Narrative.objects.filter(participant=participant, generated=True).order_by("round")
        so_far = "\n\n".join(story.text for story in told)
    lines = "\n".join(f"- {item.text or item.id}: {item.answer_word(answers[item.id])}" for item in study.items.values())
    prompt = narrative.prompt.format(name=name, answers=lines, story_so_far=so_far or "(none yet)")
    try:
        text, generated = cut(ask(narrative, prompt), narrative.max_words), True
    except (OSError, ValueError, KeyError, IndexError) as error:  # no answer, a slow one, or an answer we can't read
        logger.warning("narrative.toml: the model gave no story, so the fallback is shown: %r", error)
        text, generated = narrative.fallback, False
    return Narrative.objects.create(participant=participant, round=participant.round, character=name, text=text, generated=generated)


def ask(narrative: Settings, prompt: str) -> str:
    """The model's answer to the prompt, through the OpenAI-style chat API that Ollama and OpenAI both offer."""
    headers = {"Content-Type": "application/json"}
    if settings.MODEL_API_KEY:
        headers["Authorization"] = f"Bearer {settings.MODEL_API_KEY}"
    body = json.dumps({"model": narrative.model, "messages": [{"role": "user", "content": prompt}]}).encode()
    request = urllib.request.Request(f"{narrative.url.rstrip('/')}/v1/chat/completions", body, headers)
    with urllib.request.urlopen(request, timeout=narrative.seconds) as response:
        text = json.load(response)["choices"][0]["message"]["content"].strip()
    if not text:
        raise ValueError("the model answered with nothing")
    return text


def cut(text: str, max_words: int) -> str:
    """The text, cut off after max_words words, ending with … when it was cut."""
    words = text.split(" ")
    return text if len(words) <= max_words else " ".join(words[:max_words]) + " …"

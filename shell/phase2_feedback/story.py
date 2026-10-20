"""Feedback in the chat (feedback.toml: show = "chat" or "both"): a short story, then a small chart, each one
chat message. Pure functions, rule-based: every sentence is the study's own from feedback.toml, chosen by the
scale's state and with its blanks filled in from the participant's answers. Nothing is generated freely.
"""

from config.project import Feedback, Item
from phase2_feedback.scoring import better_is_right, scored, state


def story(feedback: Feedback, items: dict[str, Item], answers: dict[str, int]) -> str:
    """The opening, one sentence per scale, and the closing, as paragraphs.

    A sentence can name the scale ({name}), list the answers behind it in the words of their buttons
    ({answers}), or give one answer ({Q09}, by the item's id). Answers start in lower case, as they fall
    mid-sentence: "Een beetje" becomes "een beetje".
    """
    sentences = [feedback.story["opening"]]
    for scale, score in scored(feedback, items, answers):
        words = {item: mid_sentence(items[item].answer_word(answers[item])) for item in scale.items if item in answers}
        sentences.append(scale.story[state(scale, score)].format(name=scale.name, answers=", ".join(words.values()), **words))
    sentences.append(feedback.story["closing"])
    return "\n\n".join(sentences)


def mid_sentence(word: str) -> str:
    return word[:1].lower() + word[1:]


def chart(feedback: Feedback, items: dict[str, Item], answers: dict[str, int]) -> str:
    """Per scale its name with its word, and a line from worse to better that Tilbot draws (patch 0011):
    [[line left end|right end|the participant's place|the threshold's place|fine, worth or neutral]],
    places from 0 (worse) to 100 (better); no threshold leaves its place empty."""
    words = {"fine": feedback.texts["fine"], "worth": feedback.texts["worth_discussing"], "neutral": ""}
    lines = []
    for scale, score in scored(feedback, items, answers):
        kind = state(scale, score)
        left, right = scale.ends or ("", "")
        limit = "" if scale.threshold is None else f"{better_is_right(scale, scale.threshold):.1f}"
        lines.append(f"{scale.name}: {words[kind]}" if words[kind] else scale.name)
        lines.append(f"[[line {left}|{right}|{better_is_right(scale, score):.1f}|{limit}|{kind}]]")
    return "\n".join(lines)

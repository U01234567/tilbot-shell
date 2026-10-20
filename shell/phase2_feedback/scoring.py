"""Scale scores from the answers. Pure functions: the views fetch the answers, this file only counts."""

from config.project import Feedback, Item, Scale


def scale_score(scale: Scale, items: dict[str, Item], answers: dict[str, int]) -> float | None:
    """Return the scale's score from 0 to 100, or None when fewer than half of its items are answered.

    Each answer counts as its place on its item's scale, from 0 to 1; the score is the mean place times 100,
    turned around for a reverse scale. This is how the EORTC QLQ-C30 is scored, and fits any scale like it.
    """
    places = [
        (answers[item] - items[item].scale_min) / (items[item].scale_max - items[item].scale_min)
        for item in scale.items
        if item in answers
    ]
    if len(places) * 2 < len(scale.items):
        return None
    score = 100 * sum(places) / len(places)
    return 100 - score if scale.reverse else score


def worth_discussing(scale: Scale, score: float) -> bool:
    """Whether the score lies past the scale's threshold, on the side of more trouble."""
    if scale.threshold is None:
        return False
    if scale.higher == "better":
        return score < scale.threshold
    return score > scale.threshold


def scored(feedback: Feedback, items: dict[str, Item], answers: dict[str, int]) -> list[tuple[Scale, float]]:
    """Every scale with its score, leaving out a scale with too few answers."""
    scores = [(scale, scale_score(scale, items, answers)) for scale in feedback.scales]
    return [(scale, score) for scale, score in scores if score is not None]


def state(scale: Scale, score: float) -> str:
    """fine, worth or neutral (config.project.STATES): which word and which sentence of the scale apply."""
    if scale.threshold is None:
        return "neutral"
    return "worth" if worth_discussing(scale, score) else "fine"


def better_is_right(scale: Scale, value: float) -> float:
    """A score's place on a line where right is always better: so every line reads the same way."""
    return value if scale.higher == "better" else 100 - value

from config.project import Item

SAVED = "saved"  # Tilbot connector: on to the next question
HIGH = "high"  # Tilbot connector: this item's follow-up questions


def parse_answer(item: Item, raw: str) -> int:
    """Return the answer as a number on the item's scale, given as a number or as one of the item's labels.

    Raise ValueError for anything else.
    """
    text = raw.strip()
    if text in item.labels:
        return item.scale_min + item.labels.index(text)
    value = int(text)
    if not item.scale_min <= value <= item.scale_max:
        raise ValueError(f"{item.id}: {value} is not on the scale {item.scale_min}-{item.scale_max}")
    return value


def questionnaire_done(items: dict[str, Item], answers: dict[str, int]) -> bool:
    """Whether every item of questionnaire.toml has an answer: only then are there results, and a returning
    participant skips the questions."""
    return set(items) <= set(answers)


def route_after(item: Item, value: int) -> str:
    """Return the Tilbot connector to follow after this answer."""
    if item.threshold is not None and value >= item.threshold:
        return HIGH
    return SAVED

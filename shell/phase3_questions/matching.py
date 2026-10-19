"""Matching a participant's question to the knowledge base. Only closest_phrasing talks to the network."""

import json
import urllib.parse
import urllib.request

from config.project import Entry

# Seconds. The service compares the question with every phrasing on each call, which takes a moment.
TIMEOUT = 30


def closest_phrasing(question: str, phrasings: list[str], url: str) -> str | None:
    """Ask vector-similarity-intent which phrasing means most nearly the same as the question.

    Returns None when none is close enough (the service's own limit). Raises OSError or ValueError
    when the service can't be reached or answers something else.
    """
    form = urllib.parse.urlencode({"user_input": question, "intent_options": json.dumps(phrasings)})
    with urllib.request.urlopen(url, data=form.encode(), timeout=TIMEOUT) as response:
        reply = json.load(response)
    return reply["intent"] if reply else None


def by_phrasing(knowledge: tuple[Entry, ...]) -> dict[str, Entry]:
    """Every question and phrasing, with the entry it belongs to."""
    return {phrasing: entry for entry in knowledge for phrasing in entry.phrasings}


def answer_text(entry: Entry) -> str:
    """What the participant reads: the answer, and the link on its own line (patch 0007 makes it clickable)."""
    return f"{entry.answer}\n{entry.link}" if entry.link else entry.answer

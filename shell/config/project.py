"""The study settings in project/, read once at start-up.

project.toml holds what the research team checks and edits: sign-up limits and options, every text
the participant sees (so each study picks its own language), and the Tilbot project.
questionnaire.toml holds, per item, the answer scale and the threshold for follow-ups.
A mistake in either file stops the shell with an error that names the problem.
"""

import tomllib
import zoneinfo
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Item:
    """One questionnaire item. Its question text lives in Tilbot's editor."""

    id: str
    scale_min: int
    scale_max: int
    threshold: int | None  # an answer at or above this leads to follow-ups; None: never


# project-example's placeholder for [tilbot] project_id: no Tilbot project is linked yet.
NO_TILBOT_PROJECT = "0" * 32

# Every text a participant sees. project.toml must define each one under [texts].
TEXT_KEYS = (
    "sign_up", "sign_in", "sign_out", "your_id", "write_it_down", "age", "gender",
    "already_have_id", "no_id_yet", "wrong_id", "id_taken", "blocked_title", "blocked_text", "back",
)


@dataclass(frozen=True)
class Study:
    name: str
    language: str  # the language code of the pages, for example "nl" or "en"
    time_zone: str  # times are shown in this zone, for example "Europe/Amsterdam"
    transcripts: bool  # store the chat messages (encrypted), or only the answers
    tilbot_project_id: str
    age_min: int
    age_max: int
    genders: tuple[str, ...]
    texts: dict[str, str]
    items: dict[str, Item]


def load_study(project_dir: Path) -> Study:
    settings = tomllib.loads((project_dir / "project.toml").read_text(encoding="utf-8"))
    questionnaire = tomllib.loads((project_dir / "questionnaire.toml").read_text(encoding="utf-8"))
    items = [parse_item(raw) for raw in questionnaire["items"]]
    ids = [item.id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError(f"questionnaire.toml: an item id is used twice in {ids}")
    signup = settings["signup"]
    missing = [key for key in TEXT_KEYS if key not in settings["texts"]]
    if missing:
        raise ValueError(f"project.toml: [texts] lacks {', '.join(missing)}")
    return Study(
        name=settings["name"],
        language=settings["language"],
        time_zone=str(zoneinfo.ZoneInfo(settings["time_zone"])),  # an unknown zone fails here, at start-up
        transcripts=settings["transcripts"]["enabled"],
        tilbot_project_id=settings["tilbot"]["project_id"],
        age_min=signup["age_min"],
        age_max=signup["age_max"],
        genders=tuple(signup["genders"]),
        texts=settings["texts"],
        items={item.id: item for item in items},
    )


def parse_item(raw: dict) -> Item:
    scale_min, scale_max = raw["scale"]
    return Item(id=raw["id"], scale_min=scale_min, scale_max=scale_max, threshold=raw.get("threshold"))

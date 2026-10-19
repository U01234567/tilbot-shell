"""The study settings in project/, read once at start-up.

project.toml holds what the research team checks and edits: sign-up limits and options, every text
the participant sees (so each study picks its own language), and the Tilbot project.
questionnaire.toml holds, per item, the answer scale, the answer words and the threshold for follow-ups.
feedback.toml, if the study has one, holds the scales and texts of the participant's results (phase 2).
knowledge.xlsx, if the study has one, holds the questions and answers of phase 3.
A mistake in any of them stops the shell with an error that names the problem.
"""

import tomllib
import zoneinfo
from dataclasses import dataclass
from pathlib import Path

import openpyxl


@dataclass(frozen=True)
class Item:
    """One questionnaire item. Its question text lives in Tilbot's editor."""

    id: str
    scale_min: int
    scale_max: int
    threshold: int | None  # an answer at or above this leads to follow-ups; None: never
    labels: tuple[str, ...] = ()  # the answer buttons' words, lowest answer first; empty: numbers


@dataclass(frozen=True)
class Scale:
    """One scale of the results: the mean of its items' answers, from 0 to 100 (phase2_feedback/scoring.py)."""

    id: str
    name: str
    items: tuple[str, ...]
    higher: str  # "better" or "worse": what a higher score means for the participant
    reverse: bool  # True when a high answer on the items means a low score
    threshold: float | None  # worth discussing below this ("better") or above it ("worse"); None: never


@dataclass(frozen=True)
class Feedback:
    texts: dict[str, str]
    scales: tuple[Scale, ...]


@dataclass(frozen=True)
class Entry:
    """One question of the knowledge base, with the answer the participant gets for it (phase 3)."""

    id: str
    topic: str
    phrasings: tuple[str, ...]  # the question first, then other ways to ask it
    answer: str
    link: str  # a web address shown under the answer; empty: none


# project-example's placeholder for [tilbot] project_id: no Tilbot project is linked yet.
NO_TILBOT_PROJECT = "0" * 32

# Every text a participant sees. project.toml must define each one under [texts].
TEXT_KEYS = (
    "sign_up", "sign_in", "sign_out", "your_id", "write_it_down", "age", "gender",
    "already_have_id", "no_id_yet", "wrong_id", "id_taken", "blocked_title", "blocked_text", "back",
    "sign_out_check", "stay",
)
# Every text of the results panel. feedback.toml must define each one under [texts].
FEEDBACK_TEXT_KEYS = ("results", "intro", "worth_discussing", "none", "back")
HIGHER = ("better", "worse")
# The columns of knowledge.xlsx, in its first row. topic, phrasings and link may stay empty.
KNOWLEDGE_COLUMNS = ("id", "topic", "question", "phrasings", "answer", "link")


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
    feedback: Feedback | None = None  # None: the study shows no results
    knowledge: tuple[Entry, ...] | None = None  # None: the study answers no questions
    logo: bool = False  # project/theme/logo.png exists: the participant pages show it


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
        feedback=load_feedback(project_dir / "feedback.toml", ids),
        knowledge=load_knowledge(project_dir / "knowledge.xlsx"),
        logo=(project_dir / "theme" / "logo.png").exists(),
    )


def parse_item(raw: dict) -> Item:
    scale_min, scale_max = raw["scale"]
    if scale_min >= scale_max:
        raise ValueError(f"questionnaire.toml: {raw['id']} needs a scale from low to high, not {raw['scale']}")
    labels = tuple(raw.get("labels", ()))
    answers = scale_max - scale_min + 1
    if labels and len(labels) != answers:
        raise ValueError(f"questionnaire.toml: {raw['id']} has {len(labels)} labels for {answers} answers")
    return Item(id=raw["id"], scale_min=scale_min, scale_max=scale_max, threshold=raw.get("threshold"), labels=labels)


def load_feedback(path: Path, item_ids: list[str]) -> Feedback | None:
    """Read feedback.toml; a study without the file shows no results."""
    if not path.exists():
        return None
    feedback = tomllib.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in FEEDBACK_TEXT_KEYS if key not in feedback["texts"]]
    if missing:
        raise ValueError(f"feedback.toml: [texts] lacks {', '.join(missing)}")
    scales = tuple(parse_scale(raw, item_ids) for raw in feedback["scales"])
    ids = [scale.id for scale in scales]
    if len(set(ids)) != len(ids):
        raise ValueError(f"feedback.toml: a scale id is used twice in {ids}")
    return Feedback(texts=feedback["texts"], scales=scales)


def parse_scale(raw: dict, item_ids: list[str]) -> Scale:
    unknown = [item for item in raw["items"] if item not in item_ids]
    if not raw["items"]:
        raise ValueError(f"feedback.toml: scale {raw['id']} has no items")
    if unknown:
        raise ValueError(f"feedback.toml: scale {raw['id']} uses {', '.join(unknown)}, which questionnaire.toml lacks")
    if raw["higher"] not in HIGHER:
        raise ValueError(f"feedback.toml: scale {raw['id']} needs higher = \"better\" or \"worse\"")
    if not 0 <= raw.get("threshold", 0) <= 100:
        raise ValueError(f"feedback.toml: scale {raw['id']} needs a threshold from 0 to 100, like its score")
    return Scale(
        id=raw["id"],
        name=raw["name"],
        items=tuple(raw["items"]),
        higher=raw["higher"],
        reverse=raw.get("reverse", False),
        threshold=raw.get("threshold"),
    )


def load_knowledge(path: Path) -> tuple[Entry, ...] | None:
    """Read knowledge.xlsx: its first sheet, one question per row under a row of column names.

    A study without the file answers no questions. Empty rows are skipped.
    """
    if not path.exists():
        return None
    rows = list(openpyxl.load_workbook(path, data_only=True).worksheets[0].iter_rows(values_only=True))
    columns = [str(name or "").strip().lower() for name in rows[0]] if rows else []
    missing = [name for name in KNOWLEDGE_COLUMNS if name not in columns]
    if missing:
        raise ValueError(f"knowledge.xlsx: the first row lacks the column {', '.join(missing)}")
    cells = [{name: str(value or "").strip() for name, value in zip(columns, row)} for row in rows[1:]]
    entries = tuple(parse_entry(row) for row in cells if any(row.values()))
    check_unique("id", [entry.id for entry in entries])
    check_unique("question or phrasing", [p.lower() for entry in entries for p in entry.phrasings])
    return entries


def parse_entry(row: dict[str, str]) -> Entry:
    if not (row["id"] and row["question"] and row["answer"]):
        raise ValueError(f"knowledge.xlsx: every row needs an id, a question and an answer: {row}")
    others = [line.strip() for line in row["phrasings"].splitlines() if line.strip()]
    return Entry(id=row["id"], topic=row["topic"], phrasings=(row["question"], *others), answer=row["answer"], link=row["link"])


def check_unique(what: str, values: list[str]) -> None:
    twice = sorted({value for value in values if values.count(value) > 1})
    if twice:
        raise ValueError(f"knowledge.xlsx: each {what} may appear once, but these appear twice: {twice}")

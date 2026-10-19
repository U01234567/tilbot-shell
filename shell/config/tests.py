import pytest
from django.conf import settings
from django.core.management import call_command

from config.project import load_study, parse_item, parse_scale


@pytest.mark.django_db  # makemigrations checks the migration history in the database
def test_every_model_change_has_a_migration():
    call_command("makemigrations", "--check", "--dry-run")


def test_transcripts_setting_is_read_as_a_boolean(tmp_path):
    for name in ("project.toml", "questionnaire.toml"):
        text = (settings.PROJECT_DIR / name).read_text(encoding="utf-8")
        (tmp_path / name).write_text(text.replace("enabled = true", "enabled = false"), encoding="utf-8")
    assert load_study(tmp_path).transcripts is False


def test_labels_must_match_the_scale():
    with pytest.raises(ValueError, match="2 labels for 4 answers"):
        parse_item({"id": "Q09", "scale": [1, 4], "labels": ["No", "Yes"]})


def test_a_scale_needs_known_items_and_a_direction():
    with pytest.raises(ValueError, match="Q99"):
        parse_scale({"id": "pain", "name": "Pain", "items": ["Q99"], "higher": "worse"}, ["Q09"])
    with pytest.raises(ValueError, match="better"):
        parse_scale({"id": "pain", "name": "Pain", "items": ["Q09"], "higher": "up"}, ["Q09"])
    with pytest.raises(ValueError, match="0 to 100"):
        parse_scale({"id": "pain", "name": "Pain", "items": ["Q09"], "higher": "worse", "threshold": 250}, ["Q09"])


def test_without_feedback_toml_there_are_no_results(tmp_path):
    for name in ("project.toml", "questionnaire.toml"):
        (tmp_path / name).write_text((settings.PROJECT_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    assert load_study(tmp_path).feedback is None


def test_a_logo_in_the_theme_folder_is_shown(tmp_path):
    for name in ("project.toml", "questionnaire.toml"):
        (tmp_path / name).write_text((settings.PROJECT_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    assert load_study(tmp_path).logo is False
    (tmp_path / "theme").mkdir()
    (tmp_path / "theme" / "logo.png").write_bytes(b"png")
    assert load_study(tmp_path).logo is True

import pytest
from django.conf import settings
from django.core.management import call_command

from config.project import load_study


@pytest.mark.django_db  # makemigrations checks the migration history in the database
def test_every_model_change_has_a_migration():
    call_command("makemigrations", "--check", "--dry-run")


def test_transcripts_setting_is_read_as_a_boolean(tmp_path):
    for name in ("project.toml", "questionnaire.toml"):
        text = (settings.PROJECT_DIR / name).read_text(encoding="utf-8")
        (tmp_path / name).write_text(text.replace("enabled = true", "enabled = false"), encoding="utf-8")
    assert load_study(tmp_path).transcripts is False

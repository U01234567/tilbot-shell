import pytest
from django.core.management import call_command


@pytest.mark.django_db  # makemigrations checks the migration history in the database
def test_every_model_change_has_a_migration():
    call_command("makemigrations", "--check", "--dry-run")

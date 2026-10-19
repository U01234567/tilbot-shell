"""python start_shell.py erase: delete every participant's data at the end of a study (monitor/removal.py).

The study's name must be given, exactly as in project.toml, so this can't be run by accident.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from monitor.removal import erase_all


class Command(BaseCommand):
    help = "Delete every participant and all their data. Researcher accounts and Tilbot's projects stay."

    def add_arguments(self, parser):
        parser.add_argument("study_name", help="the study's name, exactly as in project.toml")

    def handle(self, study_name, **options):
        if study_name != settings.STUDY.name:
            raise CommandError(f"Nothing deleted: {study_name!r} is not this study's name.")
        erase_all()
        self.stdout.write("Deleted every participant and all their data. Delete earlier backups as the data management plan says.")

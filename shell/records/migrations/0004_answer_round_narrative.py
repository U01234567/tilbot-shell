# Written for tilbot-shell 2.2.0: rounds, and the story by a language model.

import django.db.models.deletion
import records.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_participant_link_rounds_conditions"),
        ("records", "0003_feedbackshown"),
    ]

    operations = [
        migrations.AddField(
            model_name="answer",
            name="round",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.CreateModel(
            name="Narrative",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("round", models.PositiveIntegerField()),
                ("character", models.CharField(max_length=40)),
                ("text", records.fields.EncryptedTextField()),
                ("generated", models.BooleanField()),
                ("at", models.DateTimeField(auto_now_add=True)),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="narratives",
                        to="accounts.participant",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("participant", "round"), name="one_narrative_per_round")
                ],
            },
        ),
    ]

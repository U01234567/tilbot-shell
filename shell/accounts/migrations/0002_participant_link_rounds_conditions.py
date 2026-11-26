# Written for tilbot-shell 2.2.0: sign-in by link, rounds and conditions.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="participant",
            name="code",
            field=models.CharField(max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name="participant",
            name="age",
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.AlterField(
            model_name="participant",
            name="gender",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="participant",
            name="round",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="participant",
            name="condition",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="participant",
            name="character",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]

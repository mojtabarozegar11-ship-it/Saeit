"""Record verified position IDs and whether a trade was manual or bot-driven.

Neither field authorizes live execution. Older rows remain 'unknown' with a
blank broker position ID, which cannot contribute to a fifty-trade count.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0004_four_week_challenge")]

    operations = [
        migrations.AddField(
            model_name="propexecution",
            name="external_position_id",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="propexecution",
            name="execution_origin",
            field=models.CharField(
                choices=[
                    ("unknown", "Unknown"),
                    ("manual", "Manual"),
                    ("bot", "Trader's automated strategy"),
                ],
                default="unknown",
                max_length=12,
            ),
        ),
    ]

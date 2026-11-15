"""Reconcile the existing MojPropRequest.source model with its initial schema.

The original 0041 migration omitted blank=True. Keep that published migration
immutable and express the schema state change as a proper dependent operation.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    # These were independently introduced from 0039 on some main/PR merge
    # snapshots. Join BOTH branches; otherwise Django reports parallel leaves
    # (0040_commercefunnelevent and this 0042 migration).
    dependencies = [
        ("core", "0040_commercefunnelevent"),
        ("core", "0041_mojprop_request"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mojproprequest",
            name="source",
            field=models.CharField(blank=True, default="moj-prop", max_length=80),
        ),
    ]

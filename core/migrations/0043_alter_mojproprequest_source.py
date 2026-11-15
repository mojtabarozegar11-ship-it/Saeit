"""Bring MojPropRequest.source migration state into line with its model.

The original model permits an empty source string, but the published 0041
CreateModel omitted blank=True. Preserve the published migration unmodified.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0042_merge_commercefunnel_mojprop"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mojproprequest",
            name="source",
            field=models.CharField(blank=True, default="moj-prop", max_length=80),
        ),
    ]

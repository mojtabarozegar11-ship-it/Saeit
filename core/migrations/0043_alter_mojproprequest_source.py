"""Align the live MojPropRequest.source model with the merged migration state.

This optional source label was made blank=True in the Django model. The
original core.0041 migration remained blank=False, causing makemigrations
--check to fail even after both conflicting core leaves were merged.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0042_merge_commerce_funnel_mojprop_20261115"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mojproprequest",
            name="source",
            field=models.CharField(max_length=80, blank=True, default="moj-prop"),
        ),
    ]

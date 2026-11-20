"""Store trusted source ID on broker equity snapshots.

Existing rows migrate as unknown-source ("") and must be independently
reconciled before entering any provisional profit allocation. No transfers,
wallet mutations or broker orders. Requires future owner-authorized deploy.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0006_ten_plan_enrollment"),
    ]

    operations = [
        migrations.AddField(
            model_name="propequityobservation",
            name="data_source",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]

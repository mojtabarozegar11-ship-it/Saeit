"""Version the default simulated-account rules for future Starter30 admissions.

State-only policy transition from simulation-v1 to simulation-v2. No backfill
of historical accepted records, no customer activation and no treasury action.
Do not apply to a live database without an independently restorable backup and
a separately approved, migration-aware deployment plan.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0006_unique_invoice_receivers"),
    ]

    operations = [
        migrations.AlterField(
            model_name="propsimulationaccount",
            name="policy_version",
            field=models.CharField(
                default="2026-11-21/simulation-v2",
                max_length=32,
            ),
        ),
    ]

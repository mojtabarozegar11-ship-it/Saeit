"""Align new-row policy defaults after four-week challenge enrollment migration.

This migration changes only model field defaults. It does not rewrite any
existing account's historical policy version, trade evidence or balance.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0004_four_week_challenge")]

    operations = [
        migrations.AlterField(
            model_name="propaccount",
            name="policy_version",
            field=models.CharField(default="2026-11-15/v1.2", max_length=32),
        ),
        migrations.AlterField(
            model_name="propdecisionlog",
            name="policy_version",
            field=models.CharField(default="2026-11-15/v1.2", max_length=32),
        ),
        migrations.AlterField(
            model_name="propprofitallocation",
            name="policy_version",
            field=models.CharField(default="2026-11-15/v1.2", max_length=32),
        ),
    ]

"""Align PropAccount, decision and provisional-ledger new-row defaults with policy v1.2.

This migration changes only model field defaults. It does not rewrite any
existing account's historical policy version, trade evidence or balance.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0003_social_evidence")]

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

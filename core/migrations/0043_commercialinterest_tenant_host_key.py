"""Treat a consent intake from another approved domain as a separate tenant lead.

Data-safe widening: existing four-field unique rows remain valid. No DB rows
are modified, copied, dropped or reconsented; only the database constraint changes.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0042_commercialinterest_withdrawn_at")]

    operations = [
        migrations.RemoveConstraint(
            model_name="commercialinterest",
            name="core_commercial_interest_key",
        ),
        migrations.AddConstraint(
            model_name="commercialinterest",
            constraint=models.UniqueConstraint(
                fields=("email", "offer_family", "brand", "plan_code", "source_host"),
                name="core_comint_host_key",
            ),
        ),
    ]

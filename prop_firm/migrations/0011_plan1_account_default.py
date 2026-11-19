"""Align the legacy account default with the canonical Plan 1 capital."""
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0010_reward_reserve_ledger"),
    ]

    operations = [
        migrations.AlterField(
            model_name="propaccount",
            name="starting_capital_usd",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1000.00"),
                max_digits=18,
            ),
        ),
    ]

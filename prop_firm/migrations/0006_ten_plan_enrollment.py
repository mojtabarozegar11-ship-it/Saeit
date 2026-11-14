"""Store immutable selected product SKU on the verified purchase.

Old v1.2 customers default to MOJ-PROP-01 (historical 30 TRX / $100).
No account funding, wallet, invoice creation or external side effect.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0005_trade_origin_and_position_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="propchallengeenrollment",
            name="plan_code",
            field=models.CharField(
                default="MOJ-PROP-01",
                max_length=16,
            ),
        ),
    ]

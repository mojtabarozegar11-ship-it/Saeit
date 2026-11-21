"""One native TRX receiver can belong to only one Starter30 invoice, ever.

Existing duplicated recipients MUST abort this migration. No destructive
deduplication, balance movement, or customer-record rewriting is allowed.
Apply only with a separately verified isolated DB restore and no live writers.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0005_optional_payer_wallet"),
    ]

    operations = [
        migrations.AlterField(
            model_name="propsimulationloginchallenge",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("login", "Login"),
                    ("recovery", "Recovery"),
                    ("checkout", "Verified pre-invoice email"),
                ],
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="propsimulationpayment",
            name="recipient",
            field=models.CharField(max_length=64, unique=True),
        ),
    ]

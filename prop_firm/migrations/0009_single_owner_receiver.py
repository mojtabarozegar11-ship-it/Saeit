"""Allow one owner-approved receive-only wallet to serve many invoices.

Attribution is protected by mandatory payer-wallet binding, exact amount,
two-provider finality and unique transaction IDs. The wallet remains distinct
from the owner reward-reserve wallet.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0008_simulation_stage_transition"),
    ]

    operations = [
        migrations.AlterField(
            model_name="propsimulationpayment",
            name="recipient",
            field=models.CharField(max_length=64),
        ),
    ]

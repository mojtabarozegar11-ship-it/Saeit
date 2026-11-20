from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0004_simulation_payout_commitment"),
    ]

    operations = [
        migrations.AlterField(
            model_name="propsimulationpayment",
            name="payer_hex41",
            field=models.CharField(blank=True, max_length=42, null=True),
        ),
    ]

"""Capture product-specific inquiries without making an unpaid order payable."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0042_mojprop_offer")]

    operations = [
        migrations.AddField(
            model_name="mojproprequest", name="product_id",
            field=models.PositiveBigIntegerField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="mojproprequest", name="route",
            field=models.CharField(max_length=30, choices=[
                ("blueprint", "Prop-program design"),
                ("signals", "Educational signals and market brief"),
                ("brief", "Private market brief"),
                ("audit", "mojtaba.bot.ai commercial-gate audit"),
                ("digital", "Digital product purchase inquiry"),
            ]),
        ),
    ]

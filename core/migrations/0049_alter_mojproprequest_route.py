"""Align the signal request label with the commercial prelaunch product.

State-only choice update; no table, payment, customer-data or delivery operation.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0048_alter_commercefunnelevent_event_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mojproprequest",
            name="route",
            field=models.CharField(
                max_length=30,
                choices=[
                    ("blueprint", "Prop-program design"),
                    ("signals", "Paid signal subscription (prelaunch)"),
                    ("brief", "Private market brief"),
                    ("audit", "mojtaba.bot.ai commercial-gate audit"),
                    ("digital", "Digital product purchase inquiry"),
                ],
            ),
        ),
    ]

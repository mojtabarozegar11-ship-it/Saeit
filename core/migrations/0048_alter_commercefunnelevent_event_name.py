"""Keep the funnel's newly introduced manual-lead event Django-state consistent.

Only choices metadata changes: does not add a column, alter a monetary table,
record a lead, backfill production data, or authorize a live migration.
A separate database deployment approval would still be required.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0047_mpw_guest_email_recovery"),
    ]

    operations = [
        migrations.AlterField(
            model_name="commercefunnelevent",
            name="event_name",
            field=models.CharField(
                choices=[
                    ("view_store", "Store view"),
                    ("view_item", "Product view"),
                    ("begin_checkout", "Checkout opened"),
                    ("lead_submit", "Manual lead submitted"),
                    ("invoice_created", "Invoice created"),
                    ("payment_confirmed", "Payment confirmed"),
                    ("delivery_success", "Delivery succeeded"),
                    ("delivery_failure", "Delivery failed"),
                ],
                max_length=32,
            ),
        ),
    ]

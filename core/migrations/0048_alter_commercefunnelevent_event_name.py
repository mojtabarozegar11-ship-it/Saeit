# State-only choice update generated from existing CommerceFunnelEvent model.
# No table, column, index, money or customer-data operations are introduced.
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
                max_length=32,
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
            ),
        ),
    ]

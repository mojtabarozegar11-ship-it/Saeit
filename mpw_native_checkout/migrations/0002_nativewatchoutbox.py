# Staging-only reversible migration; NOT applied to MojPlayWin production.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("mpw_native_checkout", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NativeWatchOutbox",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name="ID",
                )),
                ("action", models.CharField(max_length=16, choices=[
                    ("invoice_open", "Open"), ("invoice_closed", "Closed")
                ])),
                ("state", models.CharField(max_length=16, default="pending", choices=[
                    ("pending", "Pending"), ("delivered", "Delivered")
                ])),
                ("attempts", models.PositiveSmallIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(null=True, blank=True)),
                ("delivered_at", models.DateTimeField(null=True, blank=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("invoice", models.OneToOneField(
                    to="mpw_native_checkout.nativeinvoice",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="watch_outbox",
                )),
            ],
        ),
    ]

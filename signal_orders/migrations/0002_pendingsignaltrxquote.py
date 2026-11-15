"""Unique signed quote-proposal registry; no payment-state migration."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("signal_orders", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="PendingSignalTrxQuote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invoice_id", models.CharField(editable=False, max_length=64, unique=True)),
                ("signed_token", models.TextField(editable=False)),
                ("token_digest", models.CharField(editable=False, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("order", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="trx_quote",
                    to="signal_orders.pendingsignalorderrecord",
                )),
            ],
            options={
                "db_table": "mojtaba_signal_trx_quote_proposals",
                "default_permissions": ("view",),
            },
        ),
    ]

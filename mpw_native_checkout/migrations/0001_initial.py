# Generated for staging review. This migration is NOT applied to the live database.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0039_educationassessment_educationattempt_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NativeInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset", models.CharField(max_length=3, choices=[("ETH", "Ether (Ethereum Mainnet)"), ("TRX", "TRX (TRON Mainnet)")])),
                ("network", models.CharField(max_length=32)),
                ("merchant_address", models.CharField(max_length=100)),
                ("verified_sender_address", models.CharField(max_length=100)),
                ("amount_atomic", models.DecimalField(max_digits=50, decimal_places=0)),
                ("usd_amount", models.DecimalField(max_digits=14, decimal_places=2)),
                ("usd_per_asset", models.DecimalField(max_digits=30, decimal_places=12)),
                ("price_source", models.CharField(max_length=40)),
                ("price_observed_at", models.DateTimeField()),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("wallet_challenge_id", models.CharField(max_length=128)),
                ("sender_signature_verified_at", models.DateTimeField()),
                ("status", models.CharField(max_length=24, choices=[
                    ("awaiting", "Awaiting blockchain payment"),
                    ("paid", "Verified and paid"),
                    ("expired", "Invoice expired"),
                    ("refund_review", "Manual refund review"),
                ], default="awaiting")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="native_coin_invoice", to="core.order")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.product")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("network", "merchant_address", "amount_atomic"), name="mpw_native_unique_invoice_amount"),
                    models.CheckConstraint(condition=Q(amount_atomic__gt=0), name="mpw_native_invoice_positive"),
                    models.CheckConstraint(condition=Q(usd_amount__gt=0), name="mpw_native_invoice_positive_usd"),
                ],
            },
        ),
        migrations.CreateModel(
            name="NativeChainTransfer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("network", models.CharField(max_length=32)),
                ("tx_hash", models.CharField(max_length=80)),
                ("sender_address", models.CharField(max_length=100)),
                ("recipient_address", models.CharField(max_length=100)),
                ("amount_atomic", models.DecimalField(max_digits=50, decimal_places=0)),
                ("verified_at", models.DateTimeField()),
                ("verification_backend", models.CharField(max_length=64)),
                ("evidence_digest", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("invoice", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="chain_transfer", to="mpw_native_checkout.nativeinvoice")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("network", "tx_hash"), name="mpw_native_unique_chain_tx"),
                    models.CheckConstraint(condition=Q(amount_atomic__gt=0), name="mpw_native_transfer_positive"),
                ],
            },
        ),
    ]

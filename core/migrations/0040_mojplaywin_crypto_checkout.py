# Isolated MojPlayWin native-asset offers and invoices. No changes to other sites.
import uuid
import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0039_educationassessment_educationattempt_and_more")]

    operations = [
        migrations.CreateModel(
            name="MojCryptoOffer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("asset", models.CharField(max_length=3, choices=[("ETH", "ETH (Ethereum)"), ("TRX", "TRX (TRON)")])),
                ("atomic_amount", models.DecimalField(max_digits=40, decimal_places=0, validators=[django.core.validators.MinValueValidator(1)])),
                ("active", models.BooleanField(default=False)),
                ("private_file", models.CharField(max_length=300, blank=True, default="")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="moj_crypto_offers", to="core.product")),
            ],
        ),
        migrations.AddConstraint(
            model_name="mojcryptooffer",
            constraint=models.UniqueConstraint(fields=["product", "asset"], name="moj_crypto_offer_product_asset"),
        ),
        migrations.CreateModel(
            name="MojCryptoInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("token", models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
                ("asset", models.CharField(max_length=3)),
                ("atomic_amount", models.DecimalField(max_digits=40, decimal_places=0)),
                ("merchant_address", models.CharField(max_length=100)),
                ("status", models.CharField(max_length=24, default="awaiting_payment")),
                ("tx_hash", models.CharField(max_length=66, null=True, blank=True, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("verified_at", models.DateTimeField(null=True, blank=True)),
                ("confirmed_block", models.BigIntegerField(null=True, blank=True)),
                ("last_error", models.CharField(max_length=250, blank=True, default="")),
                ("offer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="invoices", to="core.mojcryptooffer")),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="moj_crypto_invoice", to="core.order")),
            ],
        ),
    ]

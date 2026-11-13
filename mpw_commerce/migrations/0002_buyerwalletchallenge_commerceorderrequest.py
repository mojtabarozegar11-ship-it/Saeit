"""Add durable buyer wallet ownership and idempotent order request records.

Schema declaration only. CI must never apply this to a production database.
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mpw_commerce", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BuyerWalletChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset", models.CharField(choices=[("ETH", "ETH"), ("TRX", "TRX")], max_length=3)),
                ("sender_address", models.CharField(max_length=100)),
                ("nonce", models.CharField(max_length=64, unique=True)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mpw_wallet_link_challenges", to=settings.AUTH_USER_MODEL)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="wallet_link_challenges", to="core.order")),
            ],
        ),
        migrations.CreateModel(
            name="CommerceOrderRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idempotency_key", models.UUIDField(unique=True)),
                ("requested_product_id", models.PositiveBigIntegerField()),
                ("asset", models.CharField(choices=[("ETH", "ETH"), ("TRX", "TRX")], max_length=3)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("buyer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mpw_cart_requests", to=settings.AUTH_USER_MODEL)),
                ("order", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mpw_cart_request", to="core.order")),
            ],
        ),
    ]

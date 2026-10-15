"""Buyer cart idempotency; cannot authorize payment or delivery."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("mpw_commerce", "0002_buyerwalletchallenge"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="CommerceOrderRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("idempotency_key", models.UUIDField(unique=True)),
                ("asset", models.CharField(max_length=3, choices=[("ETH", "ETH"), ("TRX", "TRX")])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("buyer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="mpw_cart_requests", to=settings.AUTH_USER_MODEL)),
                ("order", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mpw_cart_request", to="core.order")),
            ],
        ),
    ]

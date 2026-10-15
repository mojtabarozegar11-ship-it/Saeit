# Staging-only migration. Do not apply to the production checkout until release approval.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("mpw_native_checkout", "0002_nativewatchoutbox"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MerchantWalletChallenge",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset", models.CharField(max_length=3, choices=[("ETH","Ethereum"),("TRX","TRON")])),
                ("address", models.CharField(max_length=100)),
                ("nonce", models.CharField(max_length=64, unique=True)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(null=True, blank=True)),
                ("verified_at", models.DateTimeField(null=True, blank=True)),
                ("failed_attempts", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
        migrations.CreateModel(
            name="MerchantWalletProof",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset", models.CharField(max_length=3, unique=True, choices=[("ETH","Ethereum"),("TRX","TRON")])),
                ("address", models.CharField(max_length=100)),
                ("verified_at", models.DateTimeField()),
                ("signature_scheme", models.CharField(max_length=48)),
                ("signature_sha256", models.CharField(max_length=64)),
                ("owner", models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.PROTECT)),
                ("challenge", models.OneToOneField(to="mpw_native_checkout.merchantwalletchallenge", on_delete=django.db.models.deletion.PROTECT)),
            ],
        ),
    ]

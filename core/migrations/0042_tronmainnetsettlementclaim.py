"""Schema-only: irreversible canonical claim for the new TRON gateway.

Do not apply before auditing the effective MariaDB migration graph and legacy
settlement process. This migration does NOT backfill paid customer records.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0041_trongatewayinvoice")]

    operations = [
        migrations.CreateModel(
            name="TronMainnetSettlementClaim",
            fields=[
                ("txid", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("provider", models.CharField(max_length=50)),
                ("proof_digest", models.CharField(max_length=64)),
                ("claimed_at", models.DateTimeField(auto_now_add=True)),
                ("invoice", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="settlement_claim",
                    to="core.trongatewayinvoice",
                )),
                ("payment_intent", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="tron_mainnet_settlement_claim",
                    to="core.paymentintent",
                )),
            ],
            options={"verbose_name": "TRON mainnet settlement claim"},
        ),
    ]

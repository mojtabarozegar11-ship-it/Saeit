"""Schema only: isolated Starter30 native TRX order and replay-safe unverified TX claim.

NOT a deploy/merchant release. Core production migration restore remains blocked.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0047_mpw_guest_email_recovery")]

    operations = [
        migrations.CreateModel(
            name="MojPropStarter30Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order_ref", models.CharField(max_length=42, unique=True)),
                ("product", models.CharField(default="MOJPROP-STARTER30", max_length=32)),
                ("merchant_domain", models.CharField(default="mojplaywin.com", max_length=64)),
                ("merchant_id", models.CharField(default="mojplaywin-store", max_length=40)),
                ("network", models.CharField(default="tron-mainnet", max_length=20)),
                ("recipient", models.CharField(max_length=34)),
                ("payer_hex41", models.CharField(max_length=42)),
                ("amount_sun", models.PositiveBigIntegerField(default=30000000)),
                ("buyer_terms_acceptance", models.CharField(max_length=128)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("status", models.CharField(max_length=12, default="draft", choices=[
                    ("draft", "Prepared privately, not payable"),
                    ("issued", "Owner-authorized invoice issued"),
                    ("settled", "Independently confirmed native TRX settlement"),
                    ("delivered", "Educational deliverable acknowledged"),
                    ("cancelled", "Cancelled without automatic refund"),
                ])),
                ("lead", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="starter30_orders",
                    to="core.mojproprequest",
                )),
            ],
            options={"default_permissions": ()},
        ),
        migrations.CreateModel(
            name="MojPropStarter30TxClaim",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("txid", models.CharField(max_length=64, unique=True)),
                ("network", models.CharField(default="tron-mainnet", max_length=20)),
                ("state", models.CharField(default="unverified", max_length=12)),
                ("order", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="tx_claim",
                    to="core.mojpropstarter30order",
                )),
            ],
            options={"default_permissions": ()},
        ),
        migrations.AddConstraint(
            model_name="mojpropstarter30order",
            constraint=models.CheckConstraint(
                condition=models.Q(product="MOJPROP-STARTER30"),
                name="mojprop30_fixed_product",
            ),
        ),
        migrations.AddConstraint(
            model_name="mojpropstarter30order",
            constraint=models.CheckConstraint(
                condition=models.Q(amount_sun=30000000),
                name="mojprop30_fixed_native_sun",
            ),
        ),
        migrations.AddConstraint(
            model_name="mojpropstarter30order",
            constraint=models.CheckConstraint(
                condition=models.Q(network="tron-mainnet"),
                name="mojprop30_fixed_mainnet",
            ),
        ),
        migrations.AddConstraint(
            model_name="mojpropstarter30order",
            constraint=models.CheckConstraint(
                condition=models.Q(merchant_domain="mojplaywin.com")
                & models.Q(merchant_id="mojplaywin-store"),
                name="mojprop30_fixed_merchant",
            ),
        ),
        migrations.AddConstraint(
            model_name="mojpropstarter30order",
            constraint=models.CheckConstraint(
                # Source-only hold: cannot be falsely marked paid or delivered.
                condition=models.Q(status="draft"),
                name="mojprop30_draft_only",
            ),
        ),
        migrations.AddConstraint(
            model_name="mojpropstarter30txclaim",
            constraint=models.CheckConstraint(
                condition=models.Q(network="tron-mainnet"),
                name="mojprop30_tx_mainnet_only",
            ),
        ),
        migrations.AddConstraint(
            model_name="mojpropstarter30txclaim",
            constraint=models.CheckConstraint(
                condition=models.Q(state="unverified"),
                name="mojprop30_tx_never_auto_credit",
            ),
        ),
    ]

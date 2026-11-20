from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0008_prospect_contact_intake"),
    ]

    operations = [
        migrations.CreateModel(
            name="TronSettlementLedger",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("network", models.CharField(max_length=24)),
                ("tx_hash", models.CharField(max_length=128)),
                ("amount_sun", models.PositiveBigIntegerField()),
                ("evidence_digest", models.CharField(max_length=64)),
                ("trusted_reconciler_attestation", models.BooleanField(default=False)),
                ("verified_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("network", "tx_hash"),
                        name="mp_tron_network_tx_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(amount_sun=30000000),
                        name="mp_tron_plan1_amount_exact",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="PropPlan1Invoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_ref", models.CharField(max_length=96, unique=True)),
                ("buyer_email", models.EmailField(max_length=254)),
                ("product_code", models.CharField(default="MOJ-PROP-01", max_length=16)),
                ("contract_version", models.CharField(max_length=32)),
                ("network", models.CharField(max_length=24)),
                ("amount_sun", models.PositiveBigIntegerField(default=30000000)),
                ("recipient", models.CharField(max_length=64)),
                ("buyer_terms_acceptance", models.BooleanField(default=False)),
                ("contract_digest", models.CharField(max_length=64)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("paid", "Paid"), ("expired", "Expired")],
                    default="pending", max_length=12,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(amount_sun=30000000),
                        name="mp_plan1_invoice_amount_exact",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="PropPlan1Receipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("invoice", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="receipt",
                    to="prop_firm.propplan1invoice",
                )),
                ("ledger", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="receipt",
                    to="prop_firm.tronsettlementledger",
                )),
            ],
        ),
    ]

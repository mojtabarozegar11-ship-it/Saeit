"""Create-only native Plan1 invoice and atomic settlement tables.

No migration may run against production before off-host SQL+media recovery,
storage validation, valid foreign TRX legal clearance, and deployment approval.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("prop_firm", "0011_v141_contact_leads"),
    ]

    operations = [
        migrations.CreateModel(
            name="PropV141NativeOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=56, unique=True)),
                ("product_code", models.CharField(default="MOJ-PROP-01",
                                                   max_length=20)),
                ("country_of_residence", models.CharField(max_length=2)),
                ("recipient", models.CharField(max_length=34)),
                ("payer_hex41", models.CharField(max_length=42)),
                ("amount_sun", models.PositiveBigIntegerField(default=30_000_000)),
                ("terms_version", models.CharField(max_length=96)),
                ("terms_sha256", models.CharField(max_length=64)),
                ("consent_digest", models.CharField(max_length=64)),
                ("payer_wallet_attestation_sha256", models.CharField(max_length=64)),
                ("legal_clearance_digest", models.CharField(max_length=64)),
                ("clearance_document_ref", models.CharField(max_length=128)),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("status", models.CharField(
                    choices=[("issued", "Issued"), ("settled", "Settled")],
                    default="issued", max_length=18)),
                ("settled_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("buyer", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="mojprop_v141_native_orders",
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "indexes": [models.Index(fields=["buyer", "-created_at"],
                                         name="mp_v141_pay_buyer")],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(amount_sun=30_000_000),
                        name="mp_v141_pay_30m_sun"),
                    models.CheckConstraint(
                        condition=models.Q(product_code="MOJ-PROP-01"),
                        name="mp_v141_pay_correct_sku"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PropGlobalTRXSettlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("network", models.CharField(default="tron-mainnet",
                                             max_length=24)),
                ("txid", models.CharField(max_length=64)),
                ("product_code", models.CharField(max_length=32)),
                ("order_reference", models.CharField(max_length=96, unique=True)),
                ("evidence_sha256", models.CharField(max_length=64)),
                ("solidified_block", models.PositiveBigIntegerField()),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=["network", "txid"],
                        name="mp_global_trx_txid_unique"),
                    models.CheckConstraint(
                        condition=models.Q(solidified_block__gt=0),
                        name="mp_global_trx_block_positive"),
                ],
            },
        ),
        migrations.CreateModel(
            name="PropV141NativeReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("confirmed_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="native_receipt",
                    to="prop_firm.propv141nativeorder")),
                ("settlement", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="mojprop_plan1_native_receipt",
                    to="prop_firm.propglobaltrxsettlement")),
                ("state", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="native_paid_receipt",
                    to="prop_firm.propv141simstate")),
                ("book", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="native_paid_receipt",
                    to="prop_firm.propv141virtualbook")),
            ],
        ),
    ]

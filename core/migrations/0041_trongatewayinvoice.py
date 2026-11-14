from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0040_commercefunnelevent")]
    operations = [
        migrations.CreateModel(
            name="TronGatewayInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("buyer_email", models.EmailField(max_length=254)),
                ("buyer_email_sha", models.CharField(db_index=True, max_length=64)),
                ("candidate_txid", models.CharField(blank=True, default="", max_length=64)),
                ("source_host", models.CharField(max_length=150)),
                ("language", models.CharField(max_length=2)),
                ("receiver", models.CharField(max_length=34)),
                ("amount_sun", models.BigIntegerField()),
                ("issued_ms", models.BigIntegerField()),
                ("expires_ms", models.BigIntegerField()),
                ("claim_sha256", models.CharField(max_length=64, unique=True)),
                ("quote_fingerprint", models.CharField(max_length=64)),
                ("status", models.CharField(default="email_pending", max_length=24)),
                ("txid", models.CharField(blank=True, max_length=64, null=True, unique=True)),
                ("proof_digest", models.CharField(blank=True, default="", max_length=64)),
                ("verified_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                                                related_name="tron_gateway_invoice", to="core.order")),
                ("payment_intent", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                                                related_name="tron_gateway_invoice", to="core.paymentintent")),
            ],
        ),
        migrations.AddConstraint(
            model_name="trongatewayinvoice",
            constraint=models.UniqueConstraint(fields=("receiver", "amount_sun"),
                                               name="tron_gateway_unique_quote_amount"),
        ),
        migrations.AddIndex(
            model_name="trongatewayinvoice",
            index=models.Index(fields=["status", "created_at"], name="tron_gateway_status_created"),
        ),
    ]

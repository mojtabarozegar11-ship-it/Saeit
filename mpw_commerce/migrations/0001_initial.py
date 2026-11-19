"""Isolated central commerce schema; never applied to a live database by CI."""
from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("core", "0039_educationassessment_educationattempt_and_more"),
    ]
    operations = [
        migrations.CreateModel(
            name="CommerceInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("asset", models.CharField(max_length=3,choices=[("ETH","ETH"),("TRX","TRX")])),
                ("network", models.CharField(max_length=32)),
                ("recipient", models.CharField(max_length=100)),
                ("expected_sender", models.CharField(max_length=100)),
                ("amount_atomic", models.CharField(max_length=50)),
                ("total_usd", models.DecimalField(max_digits=14,decimal_places=2)),
                ("quote_usd_per_asset", models.DecimalField(max_digits=30,decimal_places=12)),
                ("quote_source", models.CharField(max_length=32)),
                ("quote_observed_at", models.DateTimeField()),
                ("sender_challenge_id", models.CharField(max_length=128)),
                ("sender_signature_verified_at", models.DateTimeField()),
                ("issued_at", models.DateTimeField()),
                ("expires_at", models.DateTimeField()),
                ("status", models.CharField(max_length=16,default="awaiting",choices=[("awaiting","Awaiting blockchain verification"),("paid","Verified payment"),("expired","Expired"),("review","Review required")])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name="mpw_commerce_invoice",to="core.order")),
            ],
        ),
        migrations.CreateModel(
            name="CommerceReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("network", models.CharField(max_length=32)),
                ("tx_hash", models.CharField(max_length=80)),
                ("sender", models.CharField(max_length=100)),
                ("recipient", models.CharField(max_length=100)),
                ("amount_atomic", models.CharField(max_length=50)),
                ("evidence_digest", models.CharField(max_length=64)),
                ("backend", models.CharField(max_length=64)),
                ("finalized_at", models.DateTimeField()),
                ("invoice", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name="payment_receipt",to="mpw_commerce.commerceinvoice")),
            ],
        ),
        migrations.CreateModel(
            name="CommerceFulfillment",
            fields=[
                ("id", models.BigAutoField(auto_created=True,primary_key=True,serialize=False,verbose_name="ID")),
                ("kind", models.CharField(max_length=16,choices=[("digital","Digital download"),("subscription","Subscription"),("service","Service"),("physical","Physical goods")])),
                ("status", models.CharField(max_length=24,choices=[("ready","Digital entitlement ready"),("queued","Activation queued"),("awaiting_dispatch","Shipment awaiting dispatch"),("complete","Delivered"),("failed","Retry required")])),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("item", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,related_name="mpw_fulfillment",to="core.orderitem")),
            ],
        ),
        migrations.AddConstraint(
            model_name="commerceinvoice",
            constraint=models.UniqueConstraint(fields=("network","recipient","amount_atomic"),name="mpw_commerce_unique_native_amount"),
        ),
        migrations.AddConstraint(
            model_name="commerceinvoice",
            constraint=models.CheckConstraint(condition=Q(total_usd__gt=0),name="mpw_commerce_positive_usd"),
        ),
        migrations.AddConstraint(
            model_name="commercereceipt",
            constraint=models.UniqueConstraint(fields=("network","tx_hash"),name="mpw_commerce_unique_verified_tx"),
        ),
        migrations.AddIndex(
            model_name="commercefulfillment",
            index=models.Index(fields=["status"],name="mpw_fulfill_status_idx"),
        ),
    ]

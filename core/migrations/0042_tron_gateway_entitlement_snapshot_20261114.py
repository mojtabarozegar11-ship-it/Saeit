from django.db import migrations, models


class Migration(migrations.Migration):
    # Explicitly extend the original unified-TRON invoice table. No existing
    # invoice/payment or ledger records are deleted, rewritten or backfilled.
    dependencies = [
        ("core", "0041_trongatewayinvoice"),
    ]

    operations = [
        migrations.AddField(
            model_name="trongatewayinvoice", name="fulfillment_kind",
            field=models.CharField(max_length=16, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="trongatewayinvoice", name="asset_relpath_snapshot",
            field=models.CharField(max_length=224, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="trongatewayinvoice", name="asset_sha256_snapshot",
            field=models.CharField(max_length=64, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="trongatewayinvoice", name="rights_document_sha256_snapshot",
            field=models.CharField(max_length=64, blank=True, default=""),
        ),
        migrations.AddField(
            model_name="trongatewayinvoice", name="reconcile_attempted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="trongatewayinvoice", name="reconcile_attempts",
            field=models.PositiveIntegerField(default=0),
        ),
    ]

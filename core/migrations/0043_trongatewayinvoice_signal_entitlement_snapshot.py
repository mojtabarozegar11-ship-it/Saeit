from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0042_trongatewayinvoice_merchant_tenant_id")]

    operations = [
        migrations.AddField(
            model_name="trongatewayinvoice",
            name="signal_sku_snapshot",
            field=models.CharField(blank=True, default="", max_length=48),
        ),
        migrations.AddField(
            model_name="trongatewayinvoice",
            name="signal_term_days_snapshot",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]

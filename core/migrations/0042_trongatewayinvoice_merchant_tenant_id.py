from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0041_trongatewayinvoice")]

    operations = [
        migrations.AddField(
            model_name="trongatewayinvoice",
            name="merchant_tenant_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]

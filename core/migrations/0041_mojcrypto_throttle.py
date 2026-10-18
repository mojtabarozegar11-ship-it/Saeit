# Persistent MojPlayWin checkout abuse controls; no existing site data changed.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0040_mojplaywin_crypto_checkout")]

    operations = [
        migrations.CreateModel(
            name="MojCryptoThrottle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("action", models.CharField(max_length=36)),
                ("identity_hash", models.CharField(max_length=64)),
                ("bucket", models.BigIntegerField()),
                ("attempts", models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.AddConstraint(
            model_name="mojcryptothrottle",
            constraint=models.UniqueConstraint(
                fields=["action", "identity_hash", "bucket"], name="moj_crypto_throttle_bucket"
            ),
        ),
    ]

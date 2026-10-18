"""Add fulfillment mode to MojPlayWin crypto offers; no changes to shared Product fields."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0041_mojcrypto_throttle")]

    operations = [
        migrations.AddField(
            model_name="mojcryptooffer",
            name="fulfillment_mode",
            field=models.CharField(
                choices=[
                    ("download", "Private digital download"),
                    ("service", "Service / manually fulfilled"),
                ],
                default="download",
                max_length=12,
            ),
        ),
    ]

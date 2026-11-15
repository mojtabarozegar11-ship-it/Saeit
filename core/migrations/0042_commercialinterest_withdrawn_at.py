"""Timestamp of contact-consent withdrawal; no public financial activity."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0041_signalinterest")]

    operations = [
        migrations.AddField(
            model_name="commercialinterest",
            name="withdrawn_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
    ]

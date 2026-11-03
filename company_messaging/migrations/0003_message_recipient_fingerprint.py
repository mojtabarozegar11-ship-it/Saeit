from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("company_messaging", "0002_domestic_messengers")]
    operations = [
        # Existing pending external sends have no snapshot and fail closed
        # until explicitly reconciled; never backfill consent from today's data.
        migrations.AddField(
            model_name="message",
            name="recipient_fingerprint",
            field=models.CharField(max_length=64, blank=True, default="", editable=False),
        ),
    ]

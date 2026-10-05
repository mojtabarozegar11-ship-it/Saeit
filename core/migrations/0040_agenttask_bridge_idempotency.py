from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0039_educationassessment_educationattempt_and_more")]

    operations = [
        migrations.AddField(
            model_name="agenttask",
            name="bridge_nonce",
            field=models.CharField(blank=True, max_length=128, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="bridge_idempotency_key",
            field=models.CharField(blank=True, max_length=128, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="bridge_request_digest",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
    ]

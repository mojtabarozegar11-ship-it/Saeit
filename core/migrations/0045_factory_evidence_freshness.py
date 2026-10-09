from django.db import migrations, models
import core.models


class Migration(migrations.Migration):
    dependencies = [("core", "0044_factory_p0_release_integrity")]

    operations = [
        migrations.AddField(
            model_name="factoryevidence", name="freshness_policy_version",
            field=models.CharField(default="factory-evidence-v1", max_length=64),
        ),
        migrations.AddField(
            model_name="factoryevidence", name="valid_until",
            field=models.DateTimeField(default=core.models.factory_evidence_expiry_default),
        ),
    ]

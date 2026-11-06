from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("living_cities", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="physicalcodeclaim",
            name="reward_symbol",
            field=models.CharField(default="MOJ1", editable=False, max_length=16),
        ),
        migrations.AddField(
            model_name="physicalcodeclaim",
            name="reward_network",
            field=models.CharField(default="TRON", editable=False, max_length=24),
        ),
    ]

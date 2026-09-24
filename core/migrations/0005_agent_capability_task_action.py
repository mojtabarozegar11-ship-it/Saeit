from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0004_agent_capabilities")]
    operations = [
        migrations.AddField(
            model_name="agenttask",
            name="action_type",
            field=models.CharField(default="", max_length=100),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0005_agent_capability_task_action")]
    operations = [
        migrations.AddField(
            model_name="agenttask",
            name="capability_code",
            field=models.CharField(default="", max_length=100),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="risk_snapshot",
            field=models.CharField(default="low", max_length=10),
        ),
    ]

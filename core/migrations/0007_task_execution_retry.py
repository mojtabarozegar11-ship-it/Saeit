from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0006_task_policy_snapshot")]
    operations = [
        migrations.AddField(
            model_name="agenttask",
            name="execution_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="attempt_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="agenttask",
            name="max_attempts",
            field=models.PositiveIntegerField(default=3),
        ),
    ]

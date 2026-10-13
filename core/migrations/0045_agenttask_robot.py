from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0044_robot"),
    ]

    operations = [
        migrations.AddField(
            model_name="agenttask",
            name="robot",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tasks",
                to="core.robot",
            ),
        ),
    ]

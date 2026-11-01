# Bind private Zomorod master commands to accountable internal calendar tasks.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ecosystem_hub", "0003_mastercommand_hourly_cadence"),
        ("enterprise_portal", "0002_officeloginfailure"),
    ]

    operations = [
        migrations.AddField(
            model_name="mastercommand",
            name="task",
            field=models.OneToOneField(
                to="enterprise_portal.worktask",
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="master_command",
            ),
        ),
    ]

"""Restore MojPropRequest.source choices in migration state.

0043 intentionally aligned the nullable/blank/default/length attributes but
did not carry the model choices into migration state. Keep 0043 immutable and
make the next migration converge the historical state with the model.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0043_alter_mojproprequest_source"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mojproprequest",
            name="source",
            field=models.CharField(
                blank=True,
                choices=[
                    ("moj-prop", "Moj Prop"),
                    ("mojtaba.bot.ai", "Mojtaba.bot.ai"),
                    ("mojplaywin", "MojPlayWin"),
                ],
                default="moj-prop",
                max_length=80,
            ),
        ),
    ]

"""Converge MojPropRequest.source migration state with the branch model.

The preceding CI generated this state-alignment migration after the merge
repair. Keep the historical migrations immutable and record the exact model
field state used by this branch. `source` is intentionally free-form and has
no choices in the model.
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
                max_length=80,
                blank=True,
                default="moj-prop",
            ),
        ),
    ]

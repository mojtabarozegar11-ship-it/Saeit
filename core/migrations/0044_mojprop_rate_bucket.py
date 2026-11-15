"""Consistent abuse throttling for canonical MojPropRequest across web workers.

MojPropRequest remains the sole public conversion form; this table is only
a keyed, short-lived quota counter. Requires merged core 0042/0043 parent.
"""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0043_alter_mojproprequest_source")]
    operations = [
        migrations.CreateModel(
            name="MojPropRateBucket",
            fields=[
                ("digest", models.CharField(max_length=64, primary_key=True, editable=False, serialize=False)),
                ("count", models.PositiveSmallIntegerField(default=0, editable=False)),
                ("expires_at", models.DateTimeField(editable=False)),
            ],
            options={
                "db_table": "moj_prop_intake_rate_bucket",
                "default_permissions": ("view",),
            },
        ),
    ]

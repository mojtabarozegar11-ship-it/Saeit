# Additive schema change for isolated company login-attempt controls.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("enterprise_portal", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OfficeLoginFailure",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("failed_count", models.PositiveSmallIntegerField(default=0)),
                ("last_failed_at", models.DateTimeField()),
                ("blocked_until", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "کنترل ورود ناموفق",
                "verbose_name_plural": "کنترل امنیت ورود",
            },
        ),
    ]

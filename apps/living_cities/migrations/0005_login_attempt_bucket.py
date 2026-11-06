"""Database-wide login protection for the account-backed Living Cities API."""
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("living_cities", "0004_authoritative_tycoon"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginAttemptBucket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key_digest", models.CharField(editable=False, max_length=64, unique=True)),
                ("failures", models.PositiveSmallIntegerField(default=0)),
                ("first_failure_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("blocked_until", models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]

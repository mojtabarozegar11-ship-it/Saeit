"""Cross-worker rate control without raw client IP or Redis dependency."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0008_information_inquiries")]

    operations = [
        migrations.CreateModel(
            name="PropInterestHourlyBucket",
            fields=[
                ("digest", models.CharField(editable=False, max_length=64, primary_key=True, serialize=False)),
                ("count", models.PositiveSmallIntegerField(default=0, editable=False)),
                ("expires_at", models.DateTimeField(editable=False)),
            ],
            options={
                "db_table": "moj_prop_inquiry_hour_buckets",
                "default_permissions": ("view",),
            },
        ),
    ]

"""Synchronize 28-day verified social-review label with current model choices.

No historical review status is altered. Field remains protected by the
existing independent-review CheckConstraint.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0005_alter_policy_version_defaults")]

    operations = [
        migrations.AlterField(
            model_name="propsocialevidence",
            name="review_status",
            field=models.CharField(
                max_length=12,
                default="pending",
                choices=[
                    ("pending", "Pending independent review"),
                    ("verified", "Verified and visible for four weeks"),
                    ("rejected", "Rejected evidence"),
                ],
            ),
        ),
    ]

"""C22 align reviewed-social evidence choice label with 28-day owner contract.

This operation changes Django field metadata only, not existing user data,
payment, purchases or broker-backed capital.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0004_four_week_challenge")]

    operations = [
        migrations.AlterField(
            model_name="propsocialevidence",
            name="review_status",
            field=models.CharField(
                max_length=12, default="pending",
                choices=[
                    ("pending", "Pending independent review"),
                    ("verified", "Verified and visible for four weeks"),
                    ("rejected", "Rejected evidence"),
                ],
            ),
        ),
    ]

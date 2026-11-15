"""Non-financial inquiry only, no customer funded-account or payment grants."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0007_equity_broker_source")]

    operations = [
        migrations.CreateModel(
            name="PropInformationInquiry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(editable=False, max_length=254)),
                ("email_digest", models.CharField(editable=False, max_length=64, unique=True)),
                ("consent_version", models.CharField(editable=False, max_length=40)),
                ("status", models.CharField(
                    choices=[("unreviewed", "Unreviewed"), ("handled", "Handled")],
                    default="unreviewed", editable=False, max_length=16,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
                ("expires_at", models.DateTimeField(editable=False)),
            ],
            options={
                "db_table": "moj_prop_information_inquiries",
                "default_permissions": ("view",),
                "indexes": [models.Index(fields=("status", "created_at"), name="mp_inquiry_status_time")],
            },
        ),
    ]

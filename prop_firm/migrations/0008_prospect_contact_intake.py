"""Add privacy-minimized prospective-buyer intake, separate from settlement."""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0007_equity_broker_source")]
    operations = [
        migrations.CreateModel(
            name="PropInterest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("plan_code", models.CharField(default="MOJ-PROP-01", max_length=16)),
                ("consent_version", models.CharField(default="moj-prop-interest-v1", max_length=40)),
                ("source_language", models.CharField(default="en", max_length=8)),
                ("status", models.CharField(choices=[
                    ("new", "New"), ("contacted", "Contacted"),
                    ("withdrawn", "Consent withdrawn"),
                ], default="new", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"indexes": [models.Index(fields=("status", "-created_at"),
                                              name="mp_interest_status")]},
        ),
    ]

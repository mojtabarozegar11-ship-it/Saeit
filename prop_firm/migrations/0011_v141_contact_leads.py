"""Create isolated, nonpayable Plan 1 contact-intent table; no legacy edits."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0010_v141_virtual_tenant_books")]
    operations = [
        migrations.CreateModel(
            name="PropV141Interest",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("plan_code", models.CharField(
                    default="MOJ-PROP-01", max_length=16)),
                ("consent_version", models.CharField(
                    default="moj-prop-v141-info-contact-v1", max_length=48)),
                ("source_language", models.CharField(
                    default="en", max_length=2)),
                ("status", models.CharField(max_length=16, default="new",
                    choices=[("new", "New"), ("contacted", "Contacted"),
                             ("withdrawn", "Consent withdrawn")])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"indexes": [
                models.Index(fields=("status", "-created_at"),
                             name="mp_v141_interest_st"),
            ]},
        ),
    ]

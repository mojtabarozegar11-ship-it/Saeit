"""Create shared non-payment CRM for signal and MOJ PROP information requests."""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("core", "0040_commercefunnelevent")]
    operations = [
        migrations.CreateModel(
            name="CommercialInterest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254)),
                ("offer_family", models.CharField(max_length=16, default="signals",
                    choices=[("signals","Market signal information"),
                             ("moj_prop","MOJ PROP Plan 1 information")])),
                ("brand", models.CharField(max_length=24)),
                ("plan_code", models.CharField(max_length=40)),
                ("consent_version", models.CharField(
                    default="mojtaba-signals-interest-v1", max_length=40)),
                ("source_language", models.CharField(default="en", max_length=2)),
                ("source_host", models.CharField(max_length=100)),
                ("status", models.CharField(default="new", max_length=16,
                    choices=[("new","New"),("contacted","Contacted"),
                             ("withdrawn","Consent withdrawn")])),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [models.UniqueConstraint(
                    fields=("email","offer_family","brand","plan_code"),
                    name="core_commercial_interest_key")],
                "indexes": [models.Index(fields=("status","-created_at"),
                    name="core_signal_interest_status")],
            },
        ),
    ]

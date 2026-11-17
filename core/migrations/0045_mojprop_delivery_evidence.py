"""Private deliverable handoff audit; no mail, blockchain or publishing."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0044_mojprop_acceptance_evidence")]
    operations = [
        migrations.CreateModel(
            name="MojPropDeliveryEvidence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("artifact_sha256", models.CharField(max_length=64)),
                ("artifact_name", models.CharField(max_length=180)),
                ("status", models.CharField(max_length=16, default="prepared", choices=[
                    ("prepared", "Artifact prepared privately"),
                    ("sent", "External handoff recorded"),
                    ("acknowledged", "Customer acknowledgement recorded"),
                ])),
                ("clearance_reference", models.CharField(max_length=180, blank=True, default="")),
                ("handoff_reference", models.CharField(max_length=180, blank=True, default="")),
                ("handed_off_at", models.DateTimeField(null=True, blank=True)),
                ("acknowledgment_reference", models.CharField(max_length=180, blank=True, default="")),
                ("acknowledged_at", models.DateTimeField(null=True, blank=True)),
                ("offer", models.OneToOneField(
                    to="core.mojpropoffer", related_name="delivery_evidence",
                    on_delete=django.db.models.deletion.PROTECT,
                )),
            ],
        ),
    ]

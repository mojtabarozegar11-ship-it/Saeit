"""C60 — persist non-financial Moj Prop applicant leads.

This migration stores only an applicant's contact and consent envelope. It does
not create invoices, verify KYC, authorize a broker, enable checkout, or permit
trading/payout.
"""
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PropApplicant",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("preferred_language", models.CharField(default="fa", max_length=8)),
                ("jurisdiction", models.CharField(max_length=64)),
                ("source", models.CharField(max_length=64)),
                ("consent_version", models.CharField(max_length=32)),
                ("risk_disclosure_version", models.CharField(max_length=32)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("contacted", "Contacted"),
                            ("withdrawn", "Withdrawn"),
                            ("blocked", "Blocked"),
                        ],
                        default="new",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner_reviewed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["status", "-created_at"],
                        name="mp_app_status_created",
                    ),
                    models.Index(
                        fields=["jurisdiction", "-created_at"],
                        name="mp_app_juris_created",
                    ),
                ],
            },
        ),
    ]

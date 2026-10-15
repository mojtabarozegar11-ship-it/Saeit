"""Astra V2 private evidence intake, after the exact 0048 historical lineage.

Only new tables, never alters existing original factory or commercial records.
All commercial/market assertions are fail-closed at the database level.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0048_business_market_architecture"),
    ]
    operations = [
        migrations.CreateModel(
            name="FactoryQueueItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=100, unique=True)),
                ("kind", models.CharField(max_length=24, default="discovery",
                                          choices=[("discovery", "Discovery")])),
                ("stage", models.CharField(max_length=32, default="HYPOTHESIS",
                    choices=[
                        ("HYPOTHESIS", "Hypothesis"),
                        ("SOURCING", "Sourcing"),
                        ("WAITING_FOR_EVIDENCE", "Waiting for evidence"),
                        ("REVIEW_REQUIRED", "Review required"),
                        ("REJECTED", "Rejected"),
                    ])),
                ("payload_digest", models.CharField(blank=True, max_length=64)),
                ("record", models.JSONField(default=dict)),
                ("market_demand_verified", models.BooleanField(default=False)),
                ("publication_allowed", models.BooleanField(default=False)),
                ("commercial_quality_score", models.PositiveSmallIntegerField(
                    null=True, blank=True)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["kind", "stage"],
                                 name="core_astra_research_stage"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(publication_allowed=False),
                        name="core_astra_never_publish"),
                    models.CheckConstraint(
                        condition=models.Q(market_demand_verified=False),
                        name="core_astra_no_self_demand"),
                    models.CheckConstraint(
                        condition=models.Q(commercial_quality_score__isnull=True),
                        name="core_astra_quality_unset"),
                ],
            },
        ),
        migrations.CreateModel(
            name="DiscoverySnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("url", models.URLField(max_length=2048)),
                ("content_hash", models.CharField(max_length=64)),
                ("retrieved_at", models.DateTimeField()),
                ("record", models.JSONField(default=dict)),
                ("independently_verified", models.BooleanField(default=False)),
                ("hypothesis", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="discovery_snapshots", to="core.factoryqueueitem")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=["hypothesis", "url", "content_hash"],
                        name="core_astra_snapshot_unique"),
                    models.CheckConstraint(
                        condition=models.Q(independently_verified=False),
                        name="core_astra_claims_unverified"),
                ],
            },
        ),
    ]

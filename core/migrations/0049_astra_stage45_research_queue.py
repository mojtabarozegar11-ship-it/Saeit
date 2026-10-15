# Generated design for isolated Astra stage 4->5 schema validation.
# Never apply directly to the live factory without separate migration review.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0048_business_market_architecture")]

    operations = [
        migrations.CreateModel(
            name="FactoryQueueItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=100, unique=True)),
                ("kind", models.CharField(default="discovery", max_length=24)),
                ("status", models.CharField(default="RESEARCH_REQUIRED", max_length=32)),
                ("priority_score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("evidence_verified_independently", models.BooleanField(default=False)),
                ("build_authorized", models.BooleanField(default=False)),
                ("publish_authorized", models.BooleanField(default=False)),
                ("payment_authorized", models.BooleanField(default=False)),
            ],
            options={
                "indexes": [
                    models.Index(fields=["kind", "status", "id"], name="astra_queue_stage_idx"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            evidence_verified_independently=False,
                            build_authorized=False,
                            publish_authorized=False,
                            payment_authorized=False,
                        ),
                        name="astra_research_only_flags",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="DiscoverySnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("url", models.URLField(max_length=2048)),
                ("content_hash", models.CharField(max_length=64)),
                ("retrieved_at", models.DateTimeField()),
                ("record", models.JSONField(default=dict)),
                ("hypothesis", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="discovery_snapshots",
                    to="core.factoryqueueitem",
                )),
            ],
        ),
    ]

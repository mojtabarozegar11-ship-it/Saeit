"""Four manufacturing-origin routes and durable quality rework audit trail."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0040_mojplaywin_production_bank"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="mojplaywinmanufacturingorder",
            name="origin_type",
            field=models.CharField(
                choices=[
                    ("site", "Site activity and cards"),
                    ("customer", "Genuine customer production request"),
                    ("market", "Independent market demand"),
                    ("invention", "Factory-originated invention or R&D"),
                ],
                default="site", db_index=True, max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="mojplaywinmanufacturingorder",
            name="origin_reference",
            field=models.CharField(blank=True, max_length=180, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="mojplaywinmanufacturingorder",
            name="origin_description",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="mojplaywinmanufacturingorder",
            name="production_stage",
            field=models.CharField(
                choices=[
                    ("not_started", "Not sent to production"),
                    ("manufacturing", "Production in progress (operator-recorded)"),
                    ("qa_review", "Awaiting independent quality review"),
                    ("rework_required", "Quality failed — correction order open"),
                    ("rework_in_progress", "Correction in progress"),
                    ("attention_required", "Escalated expert correction, never discarded"),
                    ("qa_passed", "Quality passed — not approved for sale"),
                ],
                db_index=True, default="not_started", max_length=25,
            ),
        ),
        migrations.AddField(
            model_name="mojplaywinmanufacturingorder",
            name="quality_round",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="mojplaywinmanufacturingorder",
            name="proposal_id",
            field=models.CharField(blank=True, max_length=30, unique=True),
        ),
        migrations.AlterField(
            model_name="mojplaywinmanufacturingorder",
            name="signal",
            field=models.OneToOneField(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="manufacturing_brief",
                to="core.mojplaywinopportunitysignal",
            ),
        ),
        migrations.CreateModel(
            name="MojPlayWinQAReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("review_key", models.CharField(max_length=130, unique=True)),
                ("round_number", models.PositiveIntegerField()),
                ("verdict", models.CharField(choices=[("pass", "Verified pass"), ("fail", "Failed — repair required")], max_length=8)),
                ("artifact_reference", models.CharField(max_length=255)),
                ("summary", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("brief", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="quality_reviews", to="core.mojplaywinmanufacturingorder")),
                ("reviewed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="MojPlayWinQADefect",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("defect_code", models.CharField(max_length=70)),
                ("severity", models.CharField(choices=[("critical", "Critical"), ("major", "Major"), ("minor", "Minor")], max_length=10)),
                ("cause", models.TextField()),
                ("expected", models.TextField()),
                ("actual", models.TextField()),
                ("correction_plan", models.TextField()),
                ("resolution_evidence", models.TextField(blank=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("review", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="defects", to="core.mojplaywinqareview")),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="MojPlayWinReworkCycle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attempt_number", models.PositiveIntegerField()),
                ("state", models.CharField(choices=[("queued", "Awaiting corrective production"), ("in_progress", "Corrective production in progress"), ("needs_expert", "Expert intervention required"), ("ready_for_retest", "Fix evidence submitted; independent retest required")], default="queued", max_length=20)),
                ("instructions", models.TextField()),
                ("replacement_artifact_reference", models.CharField(blank=True, max_length=255)),
                ("fix_summary", models.TextField(blank=True)),
                ("returned_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("brief", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="rework_cycles", to="core.mojplaywinmanufacturingorder")),
                ("failed_review", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="rework_cycle", to="core.mojplaywinqareview")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddConstraint(
            model_name="mojplaywinqareview",
            constraint=models.UniqueConstraint(
                fields=("brief", "round_number"), name="mpw_qa_unique_round",
            ),
        ),
        migrations.AddConstraint(
            model_name="mojplaywinqadefect",
            constraint=models.UniqueConstraint(
                fields=("review", "defect_code"), name="mpw_defect_unique_code_per_review",
            ),
        ),
        migrations.AddConstraint(
            model_name="mojplaywinmanufacturingorder",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(origin_type="site", signal__isnull=False)
                    | models.Q(origin_type__in=("customer", "market", "invention"), signal__isnull=True)
                ),
                name="mpw_order_origin_signal_boundary",
            ),
        ),
    ]

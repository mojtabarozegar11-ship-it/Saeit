"""Add isolated MojPlayWin-only production planning tables; no data writes."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0039_educationassessment_educationattempt_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="MojPlayWinOpportunitySignal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("source_key", models.CharField(max_length=130, unique=True)),
                ("source_site", models.CharField(default="mojplaywin.com", editable=False, max_length=60)),
                ("source_kind", models.CharField(choices=[("venture", "Venture card"), ("section", "Activity section card"), ("feature", "Main feature card")], max_length=12)),
                ("source_path", models.CharField(blank=True, max_length=255)),
                ("card_title", models.CharField(max_length=300)),
                ("card_description", models.TextField()),
                ("review_note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ("source_key",),
                "verbose_name": "MojPlayWin activity signal",
                "verbose_name_plural": "MojPlayWin activity signals",
            },
        ),
        migrations.CreateModel(
            name="MojPlayWinManufacturingOrder",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("proposal_id", models.CharField(max_length=30, unique=True)),
                ("product_title", models.CharField(max_length=300)),
                ("file_format", models.CharField(max_length=35)),
                ("deliverable", models.TextField()),
                ("priority_hypothesis", models.PositiveSmallIntegerField(default=3)),
                ("status", models.CharField(choices=[("proposed_for_review", "Proposed — review required"), ("scoped", "Scoped — not approved for execution"), ("rejected", "Rejected or deferred")], db_index=True, default="proposed_for_review", max_length=30)),
                ("review_note", models.TextField(blank=True)),
                ("demand_verified", models.BooleanField(default=False)),
                ("rights_verified", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("proposed_owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="mojplaywin_manufacturing_briefs", to=settings.AUTH_USER_MODEL)),
                ("signal", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="manufacturing_brief", to="core.mojplaywinopportunitysignal")),
            ],
            options={
                "ordering": ("-priority_hypothesis", "proposal_id"),
                "verbose_name": "MojPlayWin internal manufacturing brief",
                "verbose_name_plural": "MojPlayWin internal manufacturing briefs",
            },
        ),
        migrations.AddConstraint(
            model_name="mojplaywinopportunitysignal",
            constraint=models.CheckConstraint(
                condition=models.Q(source_site="mojplaywin.com"),
                name="mpw_signal_site_only",
            ),
        ),
        migrations.AddConstraint(
            model_name="mojplaywinmanufacturingorder",
            constraint=models.CheckConstraint(
                condition=models.Q(priority_hypothesis__gte=1, priority_hypothesis__lte=5),
                name="mpw_brief_priority_1_5",
            ),
        ),
    ]

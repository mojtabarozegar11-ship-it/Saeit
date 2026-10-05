import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0041_factorymarketeligibility"),
    ]

    operations = [
        migrations.CreateModel(name="FactoryRun", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("run_id", models.CharField(max_length=64, unique=True)), ("goal", models.TextField()),
            ("status", models.CharField(default="active", max_length=20)), ("environment", models.CharField(default="development", max_length=40)),
            ("current_spec_version", models.PositiveIntegerField(default=1)), ("current_artifact_version", models.PositiveIntegerField(default=0)),
            ("product", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="factory_runs", to="core.product")),
        ]),
        migrations.AddField("agenttask", "goal", models.TextField(blank=True, default="")),
        migrations.AddField("agenttask", "factory_run", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="tasks", to="core.factoryrun")),
        migrations.AddField("agenttask", "product", models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.PROTECT, related_name="factory_tasks", to="core.product")),
        migrations.AddField("agenttask", "output_contract", models.JSONField(default=dict)),
        migrations.AddField("agenttask", "prerequisite_snapshot", models.JSONField(default=dict)),
        migrations.AddField("agenttask", "environment", models.CharField(default="development", max_length=40)),
        migrations.CreateModel(name="FactoryArtifact", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("version", models.PositiveIntegerField()), ("reference", models.CharField(max_length=500)),
            ("content_digest", models.CharField(blank=True, default="", max_length=128)), ("spec_version", models.PositiveIntegerField()),
            ("created_by_task", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="factory_artifact", to="core.agenttask")),
            ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="factory_artifacts", to="core.product")),
            ("run", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="artifacts", to="core.factoryrun")),
        ], options={"constraints": [models.UniqueConstraint(fields=("product", "version"), name="unique_factory_artifact_version")]}),
        migrations.CreateModel(name="FactoryEvidence", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("evidence_type", models.CharField(max_length=80)), ("prerequisite_digest", models.CharField(max_length=64)),
            ("spec_version", models.PositiveIntegerField(default=1)), ("artifact_version", models.PositiveIntegerField(default=0)),
            ("status", models.CharField(choices=[("valid", "Valid"), ("stale", "Stale"), ("invalid", "Invalid")], default="valid", max_length=12)),
            ("details", models.JSONField(default=dict)),
            ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="factory_evidence", to="core.product")),
            ("run", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="evidence", to="core.factoryrun")),
            ("task", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="factory_evidence", to="core.agenttask")),
        ], options={"constraints": [models.UniqueConstraint(fields=("task", "evidence_type"), name="unique_factory_evidence_per_task")]}),
        migrations.CreateModel(name="AgentToolGrant", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("capability_code", models.CharField(max_length=100)), ("tool_code", models.CharField(max_length=100)),
            ("resource_scope", models.CharField(max_length=200)), ("environment", models.CharField(max_length=40)),
            ("active", models.BooleanField(default=True)),
            ("agent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tool_grants", to="core.agent")),
        ], options={"constraints": [models.UniqueConstraint(fields=("agent", "capability_code", "tool_code", "resource_scope", "environment"), name="unique_agent_tool_resource_environment_grant")]}),
        migrations.CreateModel(name="FactoryReleaseGate", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("status", models.CharField(default="pending_owner_approval", max_length=24)),
            ("approved_at", models.DateTimeField(blank=True, null=True)),
            ("approval", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="factory_release_gates", to="core.approvalrequest")),
            ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="factory_release_approvals", to=settings.AUTH_USER_MODEL)),
            ("artifact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="release_gates", to="core.factoryartifact")),
            ("product", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="factory_release_gate", to="core.product")),
            ("run", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="release_gates", to="core.factoryrun")),
        ]),
    ]

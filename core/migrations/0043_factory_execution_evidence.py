from django.db import migrations, models
import django.utils.timezone
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0042_factory_p0_governance")]

    operations = [
        migrations.AddField(model_name="researchsource", name="retrieved_at", field=models.DateTimeField(default=django.utils.timezone.now)),
        migrations.AddField(model_name="researchsource", name="provenance", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="researchsource", name="snapshot_hash", field=models.CharField(blank=True, default="", max_length=64)),
        migrations.AddField(model_name="agenttask", name="next_retry_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(
            model_name="researchproject", name="factory_run",
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="research_project", to="core.factoryrun"),
        ),
        migrations.AddField(model_name="factoryrun", name="constraints", field=models.JSONField(default=list)),
    ]

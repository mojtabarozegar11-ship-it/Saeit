from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("command_center", "0002_management_workflows"),
        ("core", "0039_educationassessment_educationattempt_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="workitem",
            name="project",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="desk_work_items", to="core.researchproject"),
        ),
        migrations.AddField(
            model_name="workitem",
            name="resolution_reference",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]

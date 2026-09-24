from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="report",
            constraint=models.UniqueConstraint(
                fields=("project", "version"),
                name="unique_report_version_per_project",
            ),
        ),
    ]

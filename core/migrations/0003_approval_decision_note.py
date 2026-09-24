from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_research_integrity"),
    ]

    operations = [
        migrations.AddField(
            model_name="approvalrequest",
            name="decision_note",
            field=models.TextField(blank=True),
        ),
    ]

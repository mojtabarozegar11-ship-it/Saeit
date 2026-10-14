from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0045_agenttask_robot"),
    ]

    operations = [
        migrations.AlterField(
            model_name="robot",
            name="requires_owner_approval",
            field=models.BooleanField(
                default=False,
                help_text="Require owner approval for every robot task. Sensitive and high-risk actions remain approval-gated even when disabled.",
            ),
        ),
    ]

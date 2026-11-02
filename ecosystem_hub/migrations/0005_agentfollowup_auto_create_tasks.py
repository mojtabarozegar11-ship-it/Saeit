# Zomorod-only, opt-in internal follow-up receipts for scheduled agent findings.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ecosystem_hub", "0004_mastercommand_task"),
    ]

    operations = [
        migrations.AddField(
            model_name="proposedautomation",
            name="auto_create_tasks",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="AgentFollowUp",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_ref", models.CharField(max_length=160)),
                ("report", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="agent_followups", to="ecosystem_hub.assistantrun",
                )),
                ("rule", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="agent_followups", to="ecosystem_hub.proposedautomation",
                )),
                ("task", models.OneToOneField(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="agent_followup", to="enterprise_portal.worktask",
                )),
            ],
            options={
                "verbose_name": "پیگیری مستند دستیار",
                "verbose_name_plural": "مأموریت‌های پیشنهادی دستیارها",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("rule", "source_ref"),
                        name="zm_agent_followup_source_unique",
                    ),
                ],
            },
        ),
    ]

"""Additive finding-to-task link for explicit human follow-ups."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ecosystem_hub", "0002_materialpricereference_productioncostscenario"),
        ("enterprise_portal", "0002_officeloginfailure"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AssistantFollowUp",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                          serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("finding_index", models.PositiveIntegerField()),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                to=settings.AUTH_USER_MODEL)),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name="followups", to="ecosystem_hub.assistantrun")),
                ("task", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT,
                                              related_name="assistant_followup", to="enterprise_portal.worktask")),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                           to="enterprise_portal.businessunit")),
            ],
            options={
                "verbose_name": "پیگیری یافته دستیار",
                "verbose_name_plural": "پیگیری‌های انسانی دستیارها",
            },
        ),
        migrations.AddConstraint(
            model_name="assistantfollowup",
            constraint=models.UniqueConstraint(fields=("report","finding_index"),
                                               name="zm_eco_unique_followup_finding"),
        ),
    ]

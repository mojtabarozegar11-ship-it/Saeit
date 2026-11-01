# Generated for Zomorod Melal's private command receipts and hourly drafts.
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ecosystem_hub", "0002_materialpricereference_productioncostscenario"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="proposedautomation",
            name="cadence",
            field=models.CharField(
                choices=[
                    ("hourly", "ساعتی"), ("daily", "روزانه"),
                    ("weekly", "هفتگی"), ("monthly", "ماهانه"),
                ],
                default="daily",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="MasterCommand",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("request_key", models.UUIDField(default=uuid.uuid4,
                                                 editable=False, unique=True)),
                ("instruction", models.TextField(max_length=2000)),
                ("assistant_code", models.SlugField(max_length=60)),
                ("status", models.CharField(
                    choices=[
                        ("received", "فرمان دریافت شد"),
                        ("draft_ready", "گزارش پیش‌نویس آماده است"),
                    ], default="received", max_length=16,
                )),
                ("issued_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                                to=settings.AUTH_USER_MODEL)),
                ("report", models.OneToOneField(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="master_command", to="ecosystem_hub.assistantrun",
                )),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                           to="enterprise_portal.businessunit")),
            ],
            options={
                "verbose_name": "فرمان مسترایجنت",
                "verbose_name_plural": "فرمان‌های مسترایجنت",
                "ordering": ("-created_at", "-pk"),
            },
        ),
        migrations.AddIndex(
            model_name="mastercommand",
            index=models.Index(fields=["unit", "created_at"],
                               name="zm_master_unit_time_idx"),
        ),
    ]

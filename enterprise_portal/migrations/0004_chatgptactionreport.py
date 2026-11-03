# Additive, private text receipt ledger. No import of personal chat history.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("enterprise_portal", "0003_officeattachment"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ChatGPTActionReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_code", models.CharField(max_length=64, unique=True)),
                ("cycle_code", models.CharField(default="05", max_length=16)),
                ("run_reference", models.CharField(max_length=128)),
                ("occurred_at", models.DateTimeField()),
                ("title", models.CharField(max_length=240)),
                ("body", models.TextField(max_length=8000)),
                ("outcome", models.CharField(choices=[
                    ("completed", "اقدام انجام‌شده در محدوده شواهد"),
                    ("partial", "بخشی انجام‌شده"),
                    ("blocked", "متوقف یا ناموفق"),
                    ("proposed", "فقط پیشنهاد؛ اجرا نشده"),
                ], max_length=16)),
                ("evidence_url", models.URLField(max_length=500)),
                ("evidence_reviewed", models.BooleanField(default=False, help_text="صرفاً بررسی دستی سند؛ نه تضمین نتیجه تجاری")),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
                ("evidence_reviewed_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                    related_name="reviewed_chatgpt_reports", to=settings.AUTH_USER_MODEL,
                )),
                ("recorded_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="recorded_chatgpt_reports", to=settings.AUTH_USER_MODEL,
                )),
                ("unit", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="chatgpt_reports", to="enterprise_portal.businessunit",
                )),
            ],
            options={
                "verbose_name": "گزارش متنی اقدام چت‌جی‌پی‌تی",
                "verbose_name_plural": "گزارش‌های متنی اقدامات چت‌جی‌پی‌تی",
                "ordering": ("-occurred_at", "-pk"),
            },
        ),
        migrations.AddIndex(
            model_name="chatgptactionreport",
            index=models.Index(fields=("cycle_code", "occurred_at"), name="zm_chatgpt_cycle_time_idx"),
        ),
    ]

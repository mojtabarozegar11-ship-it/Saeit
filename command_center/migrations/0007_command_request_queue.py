from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [("command_center", "0006_ledger_domains")]
    operations = [migrations.CreateModel(name="CommandRequest", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("domain", models.CharField(choices=[("command", "فرمان و چرخه‌ها"), ("virtual", "سایت‌ها و کسب‌وکار مجازی"), ("physical", "شرکت و کسب‌وکار فیزیکی")], db_index=True, default="command", max_length=12)),
        ("command", models.TextField()), ("status", models.CharField(choices=[("pending", "در انتظار بررسی"), ("approved", "تأییدشده"), ("executed", "اجراشده"), ("blocked", "مسدود")], db_index=True, default="pending", max_length=12)),
        ("read_only", models.BooleanField(default=True)), ("result", models.TextField(blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("executed_at", models.DateTimeField(blank=True, null=True)),
        ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_approved_commands", to=settings.AUTH_USER_MODEL)),
        ("requested_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_command_requests", to=settings.AUTH_USER_MODEL)),
    ], options={"ordering": ("status", "-created_at")})]

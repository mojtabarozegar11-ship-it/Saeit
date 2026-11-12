from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("command_center", "0003_workitem_project_resolution"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="CycleReport", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("cycle", models.CharField(db_index=True, max_length=3)), ("project_key", models.CharField(db_index=True, max_length=80)),
            ("project_name", models.CharField(max_length=200)), ("action", models.TextField()), ("action_key", models.CharField(max_length=64)),
            ("result", models.CharField(max_length=240)), ("measure", models.CharField(max_length=160)), ("blocker", models.CharField(blank=True, max_length=240)),
            ("next_action", models.CharField(max_length=240)), ("evidence", models.TextField()), ("owner", models.CharField(max_length=160)),
            ("action_date", models.DateField()), ("readonly", models.BooleanField(default=False)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cycle_reports", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-action_date", "-created_at")}),
        migrations.CreateModel(name="CycleIssue", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("cycle", models.CharField(db_index=True, max_length=3)),
            ("project_key", models.CharField(db_index=True, max_length=80)), ("title", models.TextField()), ("owner", models.CharField(max_length=160)),
            ("observed_on", models.DateField()), ("certainty", models.CharField(choices=[("unverified", "نیازمند تأیید"), ("verified", "تأییدشده")], default="unverified", max_length=12)),
            ("source", models.TextField(blank=True)), ("next_action", models.CharField(max_length=240)), ("status", models.CharField(choices=[("open", "باز"), ("resolved", "رفع‌شده")], db_index=True, default="open", max_length=12)),
            ("resolution_evidence", models.TextField(blank=True)), ("resolved_at", models.DateTimeField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cycle_issues", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("status", "-created_at")}),
        migrations.CreateModel(name="ApprovalDecision", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("kind", models.CharField(choices=[("email", "ارسال ایمیل"), ("deploy", "استقرار و انتشار"), ("cost", "هزینه یا تعهد مالی")], db_index=True, max_length=20)),
            ("status", models.CharField(choices=[("approved", "تأیید شد"), ("rejected", "رد شد")], max_length=12)), ("approver", models.CharField(max_length=160)), ("evidence", models.TextField(blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="approval_decisions", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ("-created_at",)}),
        migrations.AddConstraint(model_name="cyclereport", constraint=models.UniqueConstraint(fields=("cycle", "project_key", "action_key"), name="uniq_cycle_project_action")),
    ]

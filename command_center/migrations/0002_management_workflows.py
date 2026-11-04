# Generated manually for the management desk workflow core.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("command_center", "0001_mpw_record"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("open", "باز"), ("in_progress", "در حال اجرا"), ("blocked", "متوقف"), ("done", "انجام‌شده")], db_index=True, default="open", max_length=20)),
                ("priority", models.CharField(choices=[("low", "کم"), ("normal", "عادی"), ("high", "زیاد"), ("urgent", "فوری")], db_index=True, default="normal", max_length=20)),
                ("due_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("source_type", models.CharField(blank=True, max_length=80)),
                ("source_id", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assignee", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="desk_work_items", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="desk_created_work_items", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("status", "-priority", "due_at", "-created_at")},
        ),
        migrations.CreateModel(
            name="InternalMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("subject", models.CharField(max_length=240)),
                ("body", models.TextField()),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("recipient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="desk_received_messages", to=settings.AUTH_USER_MODEL)),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="desk_sent_messages", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("read_at", "-created_at")},
        ),
        migrations.CreateModel(
            name="PrivateAuction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("draft", "پیش‌نویس"), ("open", "باز"), ("closed", "بسته"), ("cancelled", "لغوشده")], db_index=True, default="draft", max_length=20)),
                ("minimum_price", models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ("starts_at", models.DateTimeField(blank=True, null=True)),
                ("ends_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="desk_created_auctions", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("status", "-created_at")},
        ),
        migrations.AddIndex(model_name="workitem", index=models.Index(fields=["status", "assignee"], name="desk_work_status_assignee")),
    ]

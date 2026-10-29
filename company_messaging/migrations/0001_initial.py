from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("enterprise_portal", "0002_officeloginfailure"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="Contact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=180)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone_e164", models.CharField(blank=True, max_length=20)),
                ("telegram_chat_id", models.CharField(blank=True, max_length=80)),
                ("active", models.BooleanField(default=True)),
                ("email_consent_at", models.DateTimeField(blank=True, null=True)),
                ("sms_consent_at", models.DateTimeField(blank=True, null=True)),
                ("telegram_consent_at", models.DateTimeField(blank=True, null=True)),
                ("whatsapp_consent_at", models.DateTimeField(blank=True, null=True)),
                ("consent_evidence", models.CharField(blank=True, max_length=255)),
                ("suppressed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                           related_name="message_contacts", to="enterprise_portal.businessunit")),
            ],
            options={"ordering": ("name", "pk"), "permissions": [("manage_company_contacts", "مدیریت دفترچه مخاطبان شرکت")]},
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("key", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("channel", models.CharField(choices=[("internal", "داخلی"), ("email", "ایمیل"), ("sms", "پیامک"),
                                                     ("telegram", "تلگرام"), ("whatsapp", "واتساپ")], max_length=12)),
                ("subject", models.CharField(blank=True, max_length=200)),
                ("body", models.TextField(max_length=4096)),
                ("status", models.CharField(choices=[("queued", "در صف"), ("internal", "دریافت داخلی"),
                                                     ("sending", "در حال ارسال"), ("accepted", "پذیرش سرویس‌دهنده"),
                                                     ("blocked", "مسدود"), ("uncertain", "نیازمند بررسی")],
                                            default="queued", editable=False, max_length=12)),
                ("scheduled_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("accepted_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("read_at", models.DateTimeField(blank=True, editable=False, null=True)),
                ("attempts", models.PositiveSmallIntegerField(default=0, editable=False)),
                ("external_reference", models.CharField(blank=True, editable=False, max_length=128)),
                ("error_code", models.CharField(blank=True, editable=False, max_length=48)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("unit", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="enterprise_portal.businessunit")),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             related_name="company_messages_sent", to=settings.AUTH_USER_MODEL)),
                ("contact", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                              to="company_messaging.contact")),
                ("recipient_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                                     related_name="company_messages_received", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",), "permissions": [
                ("dispatch_company_message", "اجرای ارسال پیام از صف"),
                ("view_company_message_audit", "مشاهده رویدادهای پیام"),
            ]},
        ),
        migrations.CreateModel(
            name="MessageEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("code", models.CharField(max_length=48)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("message", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name="events", to="company_messaging.message")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(model_name="message", index=models.Index(fields=["status", "scheduled_at"], name="zm_msg_dispatch_idx")),
        migrations.AddIndex(model_name="message", index=models.Index(fields=["unit", "created_at"], name="zm_msg_unit_idx")),
    ]

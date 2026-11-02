# Additive private metadata only; no public-media storage or data migrations.
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("enterprise_portal", "0002_officeloginfailure"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="OfficeAttachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("storage_key", models.CharField(editable=False, max_length=96, unique=True)),
                ("original_name", models.CharField(max_length=180)),
                ("content_type", models.CharField(max_length=64)),
                ("size_bytes", models.PositiveIntegerField()),
                ("sha256", models.CharField(editable=False, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("letter", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attachments", to="enterprise_portal.officeletter")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "پیوست محرمانه نامه",
                "verbose_name_plural": "پیوست‌های دبیرخانه",
                "permissions": (("download_officeattachment", "دریافت فایل خصوصی دبیرخانه"),),
            },
        ),
    ]

"""Add private office SSO mapping and persistent one-use nonce ledger."""
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
            name="OfficeSsoIdentity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("php_uid", models.PositiveBigIntegerField(unique=True)),
                ("role", models.CharField(max_length=12, choices=[
                    ("admin", "مدیر"), ("accountant", "حسابدار"), ("manager", "مسئول"),
                ])),
                ("active", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="zomorod_sso_identity", to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "شناسه تأییدشده ورود یکپارچه",
                "verbose_name_plural": "شناسه‌های تأییدشده ورود یکپارچه",
            },
        ),
        migrations.CreateModel(
            name="OfficeSsoNonce",
            fields=[
                ("digest", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("expires_at", models.DateTimeField(db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "شناسه یک‌بارمصرف ورود",
                "verbose_name_plural": "شناسه‌های یک‌بارمصرف ورود",
            },
        ),
    ]

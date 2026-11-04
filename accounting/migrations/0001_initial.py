from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Account",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=20, unique=True)),
                ("name", models.CharField(max_length=160)),
                ("kind", models.CharField(choices=[("asset", "دارایی"), ("liability", "بدهی"), ("equity", "حقوق مالکانه"), ("revenue", "درآمد"), ("expense", "هزینه")], max_length=16)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ("code",)},
        ),
        migrations.CreateModel(
            name="JournalEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reference", models.CharField(max_length=40, unique=True)),
                ("occurred_on", models.DateField()),
                ("memo", models.CharField(max_length=300)),
                ("status", models.CharField(choices=[("draft", "پیش‌نویس"), ("posted", "قطعی"), ("void", "باطل")], default="draft", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("posted_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-occurred_on", "-id"), "indexes": [models.Index(fields=["status", "occurred_on"], name="accounting_j_status_4e70f8_idx")]},
        ),
        migrations.CreateModel(
            name="JournalLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("description", models.CharField(blank=True, max_length=240)),
                ("debit", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=20)),
                ("credit", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=20)),
                ("account", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="journal_lines", to="accounting.account")),
                ("entry", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="lines", to="accounting.journalentry")),
            ],
            options={"constraints": [models.CheckConstraint(condition=models.Q(("debit", 0), ("credit__gt", 0)) | models.Q(("credit", 0), ("debit__gt", 0)), name="accounting_line_one_side_only")]},
        ),
    ]

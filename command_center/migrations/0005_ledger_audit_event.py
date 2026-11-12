from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("command_center", "0004_unified_ledger"), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name="LedgerAuditEvent", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("action", models.CharField(choices=[("create", "ایجاد"), ("verify", "تأیید"), ("resolve", "رفع"), ("approve", "تصمیم")], db_index=True, max_length=12)),
        ("entity", models.CharField(db_index=True, max_length=40)), ("entity_id", models.CharField(max_length=80)),
        ("summary", models.TextField()), ("evidence", models.TextField(blank=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
        ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_audit_events", to=settings.AUTH_USER_MODEL)),
    ], options={"ordering": ("-created_at",)}),
        migrations.AddIndex(model_name="ledgerauditevent", index=models.Index(fields=["entity", "entity_id"], name="ledger_audit_entity")),
    ]

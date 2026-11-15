# Generated explicitly for the immutable pending signal order table.
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PendingSignalOrderRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_id", models.CharField(editable=False, max_length=64, unique=True)),
                ("tenant_id", models.CharField(db_index=True, editable=False, max_length=64)),
                ("offer_id", models.CharField(editable=False, max_length=64)),
                ("payload_digest", models.CharField(editable=False, max_length=64)),
                ("payload", models.JSONField(editable=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, editable=False)),
            ],
            options={
                "db_table": "mojtaba_signal_pending_orders",
                "default_permissions": ("view",),
                "indexes": [
                    models.Index(fields=("tenant_id", "created_at"), name="sig_ord_tenant_time_idx"),
                ],
            },
        ),
    ]

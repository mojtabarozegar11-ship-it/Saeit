# Created for atomic, pending-only, multi-brand signal-origin evidence.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_commercefunnelevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="SignalSourceEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("brand", models.CharField(max_length=32)),
                ("source_id", models.CharField(max_length=64)),
                ("event_id", models.CharField(max_length=100)),
                ("event_at", models.DateTimeField()),
                ("canonical_payload", models.TextField()),
                ("payload_sha256", models.CharField(max_length=64)),
                ("source_signature", models.CharField(max_length=64)),
                ("state", models.CharField(default="pending_audit", editable=False, max_length=24)),
                ("received_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [models.Index(fields=["brand", "-received_at"], name="sig_evt_brand_recent")],
                "constraints": [models.UniqueConstraint(fields=("brand", "source_id", "event_id"), name="sig_source_event_unique")],
            },
        ),
    ]

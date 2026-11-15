"""Independent consent and email confirmation for free *educational* briefs."""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0045_mojprop_delivery_evidence")]
    operations = [
        migrations.CreateModel(
            name="MojSignalFreeSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("status", models.CharField(
                    max_length=14, default="pending",
                    choices=[
                        ("pending", "Pending independent email confirmation"),
                        ("confirmed", "Confirmed free educational updates"),
                        ("unsubscribed", "Unsubscribed / suppression retained"),
                    ],
                )),
                ("nonce", models.CharField(max_length=48)),
                ("consent_at", models.DateTimeField()),
                ("consent_version", models.CharField(max_length=24, default="edu-free-v1")),
                ("confirmation_sent_at", models.DateTimeField(null=True, blank=True)),
                ("confirmed_at", models.DateTimeField(null=True, blank=True)),
                ("unsubscribed_at", models.DateTimeField(null=True, blank=True)),
                ("source", models.CharField(max_length=32, default="signal-desk")),
                ("ip_hash", models.CharField(max_length=64, default="", blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Mojtaba.bot.ai free educational subscriber", "verbose_name_plural": "Mojtaba.bot.ai free educational subscribers"},
        ),
        migrations.AddIndex(
            model_name="mojsignalfreesubscription",
            index=models.Index(fields=["status", "created_at"], name="mojsigfree_status_idx"),
        ),
        migrations.AddIndex(
            model_name="mojsignalfreesubscription",
            index=models.Index(fields=["ip_hash", "confirmation_sent_at"], name="mojsigfree_ip_sent_idx"),
        ),
    ]

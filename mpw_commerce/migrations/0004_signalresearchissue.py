from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("mpw_commerce", "0003_signalsubscription"),
    ]
    operations = [
        migrations.CreateModel(
            name="SignalResearchIssue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("record_id", models.CharField(max_length=64, unique=True)),
                ("record", models.JSONField()),
                ("fingerprint", models.CharField(max_length=64, unique=True)),
                ("source_sha256", models.CharField(max_length=64)),
                ("source_rights_reference", models.CharField(max_length=250)),
                ("published_at", models.DateTimeField(auto_now_add=True)),
                ("agent", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, to="core.agent")),
                ("reviewer", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"indexes": [
                models.Index(fields=["published_at"], name="mpw_signal_issue_date_idx"),
            ]},
        ),
    ]

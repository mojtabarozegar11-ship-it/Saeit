from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_report_provenance_knowledge"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="ApprovalGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("scope", models.JSONField(default=dict)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="approval_grants", to=settings.AUTH_USER_MODEL)),
                ("approval", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="grants", to="core.approvalrequest")),
            ],
            options={
                "indexes": [
                    models.Index(fields=["approval", "expires_at"], name="core_approv_approva_4f7e7b_idx"),
                    models.Index(fields=["actor", "expires_at"], name="core_approv_actor_i_6e1c0b_idx"),
                ],
            },
        ),
    ]
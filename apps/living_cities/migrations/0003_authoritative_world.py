from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("living_cities", "0002_claim_moj1_tron"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlayerWorld",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payload", models.JSONField(default=dict)),
                ("revision", models.PositiveBigIntegerField(default=0)),
                ("last_simulated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("owner", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="living_world", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="WorldActionReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action_key", models.CharField(max_length=96)),
                ("action_digest", models.CharField(max_length=64)),
                ("revision", models.PositiveBigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("owner", "action_key"), name="lc_world_action_owner_key")
            ]},
        ),
    ]

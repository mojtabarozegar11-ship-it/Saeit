from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("living_cities", "0003_authoritative_world"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlayerTycoon",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("payload", models.JSONField(default=dict)),
                ("revision", models.PositiveBigIntegerField(default=0)),
                ("last_simulated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("owner", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="living_tycoon", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="TycoonActionReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action_key", models.CharField(max_length=96)),
                ("action_digest", models.CharField(max_length=64)),
                ("revision", models.PositiveBigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("owner", "action_key"), name="lc_tycoon_action_owner_key")
            ]},
        ),
        migrations.CreateModel(
            name="TycoonMarketingReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("duration_seconds", models.PositiveIntegerField(default=3600)),
                ("revision", models.PositiveBigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("claim", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="marketing_receipt", to="living_cities.physicalcodeclaim")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

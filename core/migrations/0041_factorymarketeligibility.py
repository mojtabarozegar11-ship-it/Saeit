import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("core", "0040_agenttask_bridge_idempotency"),
    ]

    operations = [
        migrations.CreateModel(
            name="FactoryMarketEligibility",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("market_code", models.CharField(max_length=16, unique=True)),
                ("eligibility", models.CharField(choices=[("allowed", "Allowed"), ("pending_review", "Pending Review"), ("restricted", "Restricted"), ("unsupported", "Unsupported")], max_length=20)),
                ("evidence_reference", models.URLField(blank=True)),
                ("review_note", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField()),
                ("valid_until", models.DateTimeField(blank=True, null=True)),
                ("reviewed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="factory_market_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["market_code"]},
        ),
    ]

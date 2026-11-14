"""MOJ PROP phase/day social evidence, no automated posting or public access."""
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("prop_firm", "0002_provisional_profit_ledger"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PropSocialEvidence",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                )),
                ("platform", models.CharField(
                    choices=[("instagram", "Instagram"), ("facebook", "Facebook")],
                    max_length=12,
                )),
                ("trading_day", models.DateField(db_index=True)),
                ("post_url", models.URLField(max_length=512, unique=True)),
                ("posted_at", models.DateTimeField()),
                ("review_status", models.CharField(
                    choices=[
                        ("pending", "Pending independent review"),
                        ("verified", "Verified by independent operator"),
                        ("rejected", "Rejected evidence"),
                    ],
                    default="pending", max_length=12,
                )),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("author_verified", models.BooleanField(default=False)),
                ("public_visible", models.BooleanField(default=False)),
                ("disclosure_verified", models.BooleanField(default=False)),
                ("content_compliant", models.BooleanField(default=False)),
                ("date_verified", models.BooleanField(default=False)),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("account", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="social_evidence", to="prop_firm.propaccount",
                )),
                ("reviewed_by", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="moj_prop_reviewed_social_posts",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ("account_id", "trading_day", "platform")},
        ),
        migrations.AddConstraint(
            model_name="propsocialevidence",
            constraint=models.UniqueConstraint(
                fields=("account", "trading_day", "platform"),
                name="mp_social_day_platform_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="propsocialevidence",
            constraint=models.CheckConstraint(
                condition=~Q(review_status="verified") | (
                    Q(reviewed_by__isnull=False)
                    & Q(reviewed_at__isnull=False)
                    & Q(author_verified=True)
                    & Q(public_visible=True)
                    & Q(disclosure_verified=True)
                    & Q(content_compliant=True)
                    & Q(date_verified=True)
                ),
                name="mp_social_verified_review_gate",
            ),
        ),

        # New *prospective* accounts and logs use v1.2. Existing database
        # values remain v1.1 and are evaluated under their original contract.
        migrations.AlterField(
            model_name="propaccount", name="policy_version",
            field=models.CharField(default="2026-11-15/v1.2", max_length=32),
        ),
        migrations.AlterField(
            model_name="propdecisionlog", name="policy_version",
            field=models.CharField(default="2026-11-15/v1.2", max_length=32),
        ),
        migrations.AlterField(
            model_name="propprofitallocation", name="policy_version",
            field=models.CharField(default="2026-11-15/v1.2", max_length=32),
        ),
    ]

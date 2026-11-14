"""Convert unlaunched daily-post draft into 28-day purchase-cohort evidence.

Preserve old draft trading_day metadata rather than dropping columns. The
new unique constraint enforces one social URL per network per paid enrollment.
"""
from django.db import migrations, models
from django.db.models import Q
import django.db.models.deletion
from django.conf import settings
from django.utils import timezone


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0003_social_evidence")]

    operations = [
        migrations.CreateModel(
            name="PropChallengeEnrollment",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                )),
                ("verified_invoice_ref", models.CharField(max_length=96, unique=True)),
                ("confirmed_at", models.DateTimeField(db_index=True)),
                ("settlement_verified", models.BooleanField(default=False)),
                ("terms_version", models.CharField(
                    default="2026-11-15/v1.2", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("trader", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="challenge_enrollments", to="prop_firm.proptrader")),
            ],
        ),
        migrations.AddField(
            model_name="propaccount",
            name="challenge_enrollment",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="phase_accounts",
                to="prop_firm.propchallengeenrollment"),
        ),
        migrations.AddField(
            model_name="propsocialevidence",
            name="enrollment",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="social_posts",
                to="prop_firm.propchallengeenrollment"),
        ),
        migrations.AddField(
            model_name="propsocialevidence",
            name="continued_visibility_verified",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="propsocialevidence", name="trading_day",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterModelOptions(
            name="propsocialevidence",
            options={"ordering": ("enrollment_id", "platform")},
        ),
        migrations.RemoveConstraint(
            model_name="propsocialevidence",
            name="mp_social_day_platform_unique",
        ),
        migrations.AddConstraint(
            model_name="propsocialevidence",
            constraint=models.UniqueConstraint(
                fields=("enrollment","platform"),
                name="mp_social_enrollment_platform_unique",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="propsocialevidence",
            name="mp_social_verified_review_gate",
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
                    & Q(continued_visibility_verified=True)
                ),
                name="mp_social_verified_review_gate",
            ),
        ),
    ]

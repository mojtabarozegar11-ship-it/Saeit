"""One original post on either platform per four-week enrollment.

Refuse to migrate an existing enrollment with multiple posts. Existing proof
is never silently deleted, rewritten, approved or published.
"""
from django.db import migrations, models
from django.db.models import Count


def refuse_existing_duplicate_enrollment_posts(apps, schema_editor):
    evidence = apps.get_model("prop_firm", "PropSocialEvidence")
    collisions = (
        evidence.objects.using(schema_editor.connection.alias)
        .exclude(enrollment_id__isnull=True)
        .values("enrollment_id")
        .annotate(rows=Count("pk"))
        .filter(rows__gt=1)
    )
    if collisions.exists():
        raise RuntimeError(
            "Cannot enforce one public post per challenge: historical "
            "duplicate enrollment evidence needs manual review"
        )


class Migration(migrations.Migration):
    dependencies = [("prop_firm", "0006_alter_propsocialevidence_review_status")]

    operations = [
        migrations.RunPython(
            refuse_existing_duplicate_enrollment_posts,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RemoveConstraint(
            model_name="propsocialevidence",
            name="mp_social_enrollment_platform_unique",
        ),
        migrations.AddConstraint(
            model_name="propsocialevidence",
            constraint=models.UniqueConstraint(
                fields=("enrollment",),
                name="mp_social_enrollment_single_post",
            ),
        ),
    ]

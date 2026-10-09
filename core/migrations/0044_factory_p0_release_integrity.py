from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import core.models


def mark_factory_products(apps, schema_editor):
    Product = apps.get_model("core", "Product")
    Product.objects.filter(metadata__factory_state__isnull=False).update(factory_managed=True)
    for name in ("FactoryRun", "FactoryArtifact", "FactoryEvidence", "FactoryReleaseGate"):
        model = apps.get_model("core", name)
        product_ids = model.objects.exclude(product_id=None).values_list("product_id", flat=True).distinct()
        Product.objects.filter(pk__in=product_ids).update(factory_managed=True)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0043_factory_execution_evidence"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="product", name="factory_managed",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name="agenttoolgrant", name="valid_until",
            field=models.DateTimeField(default=core.models.factory_grant_expiry_default),
        ),
        migrations.AddField(
            model_name="agenttoolgrant", name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="approvalrequest", name="release_manifest_digest",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="approvalrequest", name="expires_at",
            field=models.DateTimeField(default=core.models.factory_approval_expiry_default),
        ),
        migrations.AddField(
            model_name="approvalrequest", name="revoked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="FactoryReleaseManifest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("spec_version", models.PositiveIntegerField()),
                ("spec_digest", models.CharField(max_length=64)),
                ("artifact_digest", models.CharField(max_length=64)),
                ("locales", models.JSONField(default=list)),
                ("markets", models.JSONField(default=list)),
                ("policy_version", models.CharField(max_length=80)),
                ("evidence_digest", models.CharField(max_length=64)),
                ("eligibility_digest", models.CharField(max_length=64)),
                ("manifest_digest", models.CharField(max_length=64, unique=True)),
                ("snapshot", models.JSONField(default=dict)),
                ("artifact", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="release_manifests", to="core.factoryartifact")),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="release_manifests", to="core.product")),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="release_manifests", to="core.factoryrun")),
            ],
            options={"abstract": False},
        ),
        migrations.AddField(
            model_name="factoryreleasegate", name="manifest",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="release_gates", to="core.factoryreleasemanifest"),
        ),
        migrations.RunPython(mark_factory_products, migrations.RunPython.noop),
    ]

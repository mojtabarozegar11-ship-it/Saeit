from django.db import migrations, models

def seed_mojplaywin(apps, schema_editor):
    BrandSite = apps.get_model("core", "BrandSite")
    BrandSite.objects.get_or_create(
        code="mojplaywin",
        defaults={
            "name": "MojPlayWin",
            "primary_domain": "mojplaywin.com",
            "aliases": ["www.mojplaywin.com"],
            "default_language": "en",
            "direction": "ltr",
            "theme_key": "mojplaywin",
            "seo_title": "MojPlayWin — Play What Comes Next",
            "seo_description": "Original games, evolving worlds and player-first experiences.",
            "active": True,
        },
    )

class Migration(migrations.Migration):
    dependencies = [("core", "0045_factory_evidence_freshness")]
    operations = [
        migrations.CreateModel(
            name="BrandSite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=120)),
                ("primary_domain", models.CharField(max_length=253, unique=True)),
                ("aliases", models.JSONField(blank=True, default=list)),
                ("default_language", models.CharField(default="en", max_length=12)),
                ("direction", models.CharField(default="ltr", max_length=3)),
                ("theme_key", models.SlugField(default="default")),
                ("seo_title", models.CharField(blank=True, max_length=200)),
                ("seo_description", models.TextField(blank=True)),
                ("active", models.BooleanField(default=True)),
            ],
        ),
        migrations.RunPython(seed_mojplaywin, migrations.RunPython.noop),
    ]

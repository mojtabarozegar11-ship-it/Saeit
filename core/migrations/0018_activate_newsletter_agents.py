from django.db import migrations


def activate(apps, schema_editor):
    Agent = apps.get_model("core", "Agent")
    Agent.objects.filter(code__in=[
        "newsletter-specialist", "newsletter-company-news",
        "newsletter-world-watch", "newsletter-unit-reports",
    ]).update(active=True)


def deactivate(apps, schema_editor):
    Agent = apps.get_model("core", "Agent")
    Agent.objects.filter(code__in=[
        "newsletter-specialist", "newsletter-company-news",
        "newsletter-world-watch", "newsletter-unit-reports",
    ]).update(active=False)


class Migration(migrations.Migration):
    dependencies = [("core", "0017_seed_newsletter_agents")]
    operations = [migrations.RunPython(activate, deactivate)]

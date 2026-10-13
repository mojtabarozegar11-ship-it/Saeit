from django.db import migrations, models


DEFAULTS = {
    "main": [
        ("خدمات", "/", "/"),
        ("آموزش", "/education/", "/education/"),
        ("هوش مصنوعی", "/agents/", "/agents/"),
        ("آب‌وهوا", "/weather/", "/weather/"),
        ("اقتصاد", "/economy/", "/economy/"),
        ("استودیو", "/studio/", "/studio/"),
        ("دانشنامه", "/knowledge/", "/knowledge/"),
        ("شرکت", "/company/", "/company/"),
    ],
    "footer_platform": [
        ("خدمات", "/", "/"),
        ("آموزش", "/education/", "/education/"),
        ("هوش مصنوعی", "/agents/", "/agents/"),
        ("آب‌وهوا", "/weather/", "/weather/"),
        ("اقتصاد", "/economy/", "/economy/"),
        ("استودیو", "/studio/", "/studio/"),
        ("دانشنامه", "/knowledge/", "/knowledge/"),
        ("شرکت", "/company/", "/company/"),
    ],
    "footer_services": [
        ("کشاورزی", "/agriculture/", "/agriculture/"),
        ("صنعت", "/industry/", "/industry/"),
        ("بازار", "/market/", "/market/"),
        ("همه خدمات", "/services/", "/services/"),
    ],
    "footer_access": [
        ("رسانه و وبلاگ شرکت", "/company/#company-content-ecosystem", ""),
        ("شرکت", "/company/", "/company/"),
        ("تماس و همکاری", "/contact/", "/contact/"),
    ],
}


def seed_navigation(apps, schema_editor):
    NavigationItem = apps.get_model("core", "SiteNavigationItem")
    for area, entries in DEFAULTS.items():
        for position, (title, url, active_prefix) in enumerate(entries, start=1):
            NavigationItem.objects.create(
                area=area,
                title=title,
                url=url,
                active_prefix=active_prefix,
                sort_order=position,
                is_active=True,
            )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0042_extend_platform_content_pages"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteNavigationItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("area", models.CharField(
                    choices=[
                        ("main", "منوی اصلی"),
                        ("footer_platform", "پاورقی ـ پلتفرم"),
                        ("footer_services", "پاورقی ـ خدمات"),
                        ("footer_access", "پاورقی ـ دسترسی"),
                    ],
                    default="main",
                    max_length=30,
                )),
                ("title", models.CharField(max_length=120)),
                ("url", models.CharField(max_length=500)),
                ("active_prefix", models.CharField(blank=True, max_length=300)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ("area", "sort_order", "id"),
                "verbose_name": "پیوند ناوبری سایت",
                "verbose_name_plural": "پیوندهای ناوبری سایت",
            },
        ),
        migrations.RunPython(seed_navigation, migrations.RunPython.noop),
    ]

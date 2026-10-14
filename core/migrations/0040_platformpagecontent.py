from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0039_educationassessment_educationattempt_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformPageContent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("page_key", models.CharField(
                    choices=[
                        ("agriculture", "کشاورزی"),
                        ("industry", "صنعت"),
                        ("research", "پژوهش"),
                        ("knowledge", "دانشنامه"),
                        ("economy", "اقتصاد"),
                        ("studio", "استودیو"),
                        ("market", "بازار"),
                        ("agents", "خدمات هوشمند"),
                    ],
                    max_length=30,
                    unique=True,
                )),
                ("kicker", models.CharField(blank=True, max_length=200)),
                ("title", models.CharField(max_length=250)),
                ("lead", models.TextField()),
                ("badge", models.CharField(blank=True, max_length=100)),
                ("heading", models.CharField(max_length=250)),
                ("body", models.TextField()),
                ("items", models.JSONField(
                    blank=True,
                    default=list,
                    help_text='JSON list of cards: [{"title": "...", "text": "..."}]',
                )),
                ("links", models.JSONField(
                    blank=True,
                    default=list,
                    help_text='JSON list of internal links: [{"title": "...", "text": "...", "url": "/path/"}]',
                )),
                ("cta_title", models.CharField(blank=True, max_length=250)),
                ("cta_text", models.TextField(blank=True)),
                ("cta_label", models.CharField(blank=True, max_length=100)),
                ("cta_url", models.CharField(blank=True, max_length=300)),
                ("seo_title", models.CharField(blank=True, max_length=250)),
                ("meta_description", models.CharField(blank=True, max_length=320)),
                ("published", models.BooleanField(default=False)),
            ],
            options={
                "verbose_name": "محتوای صفحه اصلی",
                "verbose_name_plural": "محتوای صفحات اصلی",
                "ordering": ("page_key",),
            },
        ),
    ]

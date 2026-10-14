from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0040_platformpagecontent"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlatformPageBlock",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(
                    choices=[
                        ("text", "متن"),
                        ("cards", "کارت‌ها"),
                        ("links", "پیوندها"),
                        ("callout", "دعوت به اقدام"),
                        ("faq", "پرسش‌های پرتکرار"),
                    ],
                    default="text",
                    max_length=20,
                )),
                ("title", models.CharField(blank=True, max_length=250)),
                ("body", models.TextField(blank=True)),
                ("items", models.JSONField(
                    blank=True,
                    default=list,
                    help_text="برای کارت و پیوند: فهرست JSON شامل title و text؛ برای پرسش پرتکرار: question و answer.",
                )),
                ("cta_label", models.CharField(blank=True, max_length=100)),
                ("cta_url", models.CharField(blank=True, max_length=300)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("active", models.BooleanField(default=True)),
                ("page", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="blocks",
                    to="core.platformpagecontent",
                    verbose_name="صفحه",
                )),
            ],
            options={
                "ordering": ("sort_order", "id"),
                "verbose_name": "بلوک صفحه",
                "verbose_name_plural": "بلوک‌های صفحه",
            },
        ),
    ]

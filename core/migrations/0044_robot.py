from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0043_sitenavigationitem"),
    ]

    operations = [
        migrations.CreateModel(
            name="Robot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.SlugField(unique=True)),
                ("name", models.CharField(max_length=200)),
                ("mission", models.TextField(blank=True)),
                ("connector", models.CharField(blank=True, max_length=100)),
                ("autonomy_level", models.CharField(
                    choices=[
                        ("observe", "Observe only"),
                        ("draft", "Draft and recommend"),
                        ("reversible", "Reversible non-financial actions"),
                        ("sandbox", "Sandbox execution"),
                        ("owner_approved", "Owner-approved bounded execution"),
                    ],
                    default="observe",
                    max_length=20,
                )),
                ("risk_level", models.CharField(
                    choices=[
                        ("low", "Low"),
                        ("medium", "Medium"),
                        ("high", "High"),
                        ("critical", "Critical"),
                    ],
                    default="low",
                    max_length=10,
                )),
                ("deployment_status", models.CharField(
                    choices=[
                        ("draft", "Draft"),
                        ("sandbox", "Sandbox"),
                        ("deployed", "Deployed"),
                        ("paused", "Paused"),
                        ("retired", "Retired"),
                    ],
                    default="draft",
                    max_length=20,
                )),
                ("requires_owner_approval", models.BooleanField(default=True)),
                ("budget_limit", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("credential_reference", models.CharField(
                    blank=True,
                    help_text="Reference to a secret manager entry only. Never store a credential here.",
                    max_length=255,
                )),
                ("agent", models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="robots",
                    to="core.agent",
                )),
            ],
            options={
                "verbose_name": "ربات اجرایی",
                "verbose_name_plural": "ربات‌های اجرایی",
                "ordering": ("code",),
            },
        ),
    ]

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("core", "0015_paymentwebhookevent")]

    operations = [
        migrations.CreateModel(
            name="DailyContentPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("run_date", models.DateField()),
                ("company_topic", models.CharField(max_length=300)),
                ("ceo_topic", models.CharField(max_length=300)),
                ("company_title", models.CharField(blank=True, max_length=300)),
                ("ceo_title", models.CharField(blank=True, max_length=300)),
                ("status", models.CharField(default="planned", max_length=30)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_content_plans", to="core.researchproject")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("project", "run_date"), name="unique_daily_content_plan_per_project_day")]},
        ),
        migrations.CreateModel(
            name="DailyContentDraft",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("kind", models.CharField(choices=[("company", "company"), ("ceo", "ceo")], max_length=20)),
                ("title", models.CharField(max_length=300)),
                ("slug", models.SlugField(unique=True)),
                ("content", models.TextField()),
                ("status", models.CharField(default="draft", max_length=30)),
                ("knowledge_article", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="daily_content_draft", to="core.knowledgearticle")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="drafts", to="core.dailycontentplan")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("plan", "kind"), name="unique_daily_content_draft_kind")]},
        ),
    ]

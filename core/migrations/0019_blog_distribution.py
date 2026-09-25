import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q
from django.utils.text import slugify
from django.utils import timezone

from core.blog_seed import TOPICS, EXTERNALS


def seed(apps, schema_editor):
    BlogPage = apps.get_model("core", "BlogPage")
    ExternalBlogTarget = apps.get_model("core", "ExternalBlogTarget")
    for i, title in enumerate(TOPICS, 1):
        BlogPage.objects.get_or_create(code=f"internal-{i:02d}", defaults={"title": title, "slug": slugify(title, allow_unicode=True), "description": f"صفحه تخصصی {title} در وبلاگ شرکت.", "language": "fa", "seo_priority": i})
    for code, name, language in EXTERNALS:
        ExternalBlogTarget.objects.get_or_create(code=code, defaults={"name": name, "language": language, "active": False, "authorized": False, "notes": "برای انتشار خارجی، URL و مجوز انتشار مالک باید ثبت شود."})


def unseed(apps, schema_editor):
    BlogPage = apps.get_model("core", "BlogPage")
    ExternalBlogTarget = apps.get_model("core", "ExternalBlogTarget")
    BlogPage.objects.filter(code__startswith="internal-").delete()
    ExternalBlogTarget.objects.filter(code__startswith="global-").delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0018_activate_newsletter_agents")]
    operations = [
        migrations.CreateModel(name="BlogPage", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("code", models.CharField(max_length=40, unique=True)), ("title", models.CharField(max_length=250)), ("slug", models.SlugField(max_length=180, unique=True)), ("description", models.TextField(blank=True)), ("language", models.CharField(choices=[("fa", "فارسی"), ("en", "English"), ("ar", "العربية"), ("es", "Español"), ("fr", "Français"), ("de", "Deutsch"), ("zh", "中文"), ("ru", "Русский"), ("tr", "Türkçe"), ("it", "Italiano")], default="fa", max_length=8)), ("active", models.BooleanField(default=True)), ("seo_priority", models.PositiveIntegerField(default=50))], options={"ordering": ("seo_priority", "code")}),
        migrations.CreateModel(name="ExternalBlogTarget", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("code", models.CharField(max_length=40, unique=True)), ("name", models.CharField(max_length=250)), ("url", models.URLField(blank=True)), ("language", models.CharField(choices=[("fa", "فارسی"), ("en", "English"), ("ar", "العربية"), ("es", "Español"), ("fr", "Français"), ("de", "Deutsch"), ("zh", "中文"), ("ru", "Русский"), ("tr", "Türkçe"), ("it", "Italiano")], default="en", max_length=8)), ("publisher_type", models.CharField(default="authorized_blog", max_length=40)), ("active", models.BooleanField(default=False)), ("authorized", models.BooleanField(default=False)), ("endpoint", models.URLField(blank=True)), ("notes", models.TextField(blank=True))]),
        migrations.CreateModel(name="BlogTranslation", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("language", models.CharField(choices=[("fa", "فارسی"), ("en", "English"), ("ar", "العربية"), ("es", "Español"), ("fr", "Français"), ("de", "Deutsch"), ("zh", "中文"), ("ru", "Русский"), ("tr", "Türkçe"), ("it", "Italiano")], max_length=8)), ("title", models.CharField(max_length=500)), ("body", models.TextField()), ("meta_description", models.TextField(blank=True)), ("seo_keywords", models.JSONField(default=list)), ("canonical_url", models.URLField(blank=True)), ("published_at", models.DateTimeField(blank=True, null=True)), ("status", models.CharField(default="draft", max_length=20)), ("page", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="translations", to="core.blogpage"))], options={"constraints": [models.UniqueConstraint(fields=("page", "language"), name="unique_blog_page_language")]}),
        migrations.CreateModel(name="BlogDistributionPlan", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("internal_count", models.PositiveIntegerField(default=50)), ("external_count", models.PositiveIntegerField(default=10)), ("languages", models.JSONField(default=list)), ("requires_owner_approval", models.BooleanField(default=True)), ("status", models.CharField(default="draft", max_length=20)), ("created_at", models.DateTimeField(auto_now_add=True)), ("story", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="distribution_plan", to="core.newsletterstory"))]),
        migrations.CreateModel(name="BlogPublication", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("language", models.CharField(choices=[("fa", "فارسی"), ("en", "English"), ("ar", "العربية"), ("es", "Español"), ("fr", "Français"), ("de", "Deutsch"), ("zh", "中文"), ("ru", "Русский"), ("tr", "Türkçe"), ("it", "Italiano")], max_length=8)), ("status", models.CharField(default="queued", max_length=20)), ("canonical_url", models.URLField(blank=True)), ("external_id", models.CharField(blank=True, max_length=300)), ("created_at", models.DateTimeField(auto_now_add=True)), ("published_at", models.DateTimeField(blank=True, null=True)), ("error", models.TextField(blank=True)), ("external_target", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="publications", to="core.externalblogtarget")), ("internal_page", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="publications", to="core.blogpage")), ("story", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blog_publications", to="core.newsletterstory"))], options={"constraints": [models.CheckConstraint(condition=Q(("internal_page__isnull", False), ("external_target__isnull", False), _connector="OR"), name="blog_publication_has_target")], "indexes": [models.Index(fields=["status", "language"], name="core_blogpub_status_lang_idx")]}),
        migrations.RunPython(seed, unseed),
    ]

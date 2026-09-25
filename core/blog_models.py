from django.db import models


LANGUAGES = (("fa", "فارسی"), ("en", "English"), ("ar", "العربية"), ("es", "Español"), ("fr", "Français"), ("de", "Deutsch"), ("zh", "中文"), ("ru", "Русский"), ("tr", "Türkçe"), ("it", "Italiano"))


class BlogPage(models.Model):
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    language = models.CharField(max_length=8, choices=LANGUAGES, default="fa")
    active = models.BooleanField(default=True)
    seo_priority = models.PositiveIntegerField(default=50)

    class Meta:
        ordering = ("seo_priority", "code")


class BlogTranslation(models.Model):
    page = models.ForeignKey(BlogPage, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(max_length=8, choices=LANGUAGES)
    title = models.CharField(max_length=500)
    body = models.TextField()
    meta_description = models.TextField(blank=True)
    seo_keywords = models.JSONField(default=list)
    canonical_url = models.URLField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default="draft")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("page", "language"), name="unique_blog_page_language")]


class ExternalBlogTarget(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=250)
    url = models.URLField(blank=True)
    language = models.CharField(max_length=8, choices=LANGUAGES, default="en")
    publisher_type = models.CharField(max_length=40, default="authorized_blog")
    active = models.BooleanField(default=False)
    authorized = models.BooleanField(default=False)
    endpoint = models.URLField(blank=True)
    notes = models.TextField(blank=True)


class BlogPublication(models.Model):
    story = models.ForeignKey("NewsletterStory", on_delete=models.CASCADE, related_name="blog_publications")
    internal_page = models.ForeignKey(BlogPage, on_delete=models.PROTECT, null=True, blank=True, related_name="publications")
    external_target = models.ForeignKey(ExternalBlogTarget, on_delete=models.PROTECT, null=True, blank=True, related_name="publications")
    language = models.CharField(max_length=8, choices=LANGUAGES)
    status = models.CharField(max_length=20, default="queued")
    canonical_url = models.URLField(blank=True)
    external_id = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)

    class Meta:
        constraints = [models.CheckConstraint(check=models.Q(internal_page__isnull=False) | models.Q(external_target__isnull=False), name="blog_publication_has_target")]
        indexes = [models.Index(fields=("status", "language"))]


class BlogDistributionPlan(models.Model):
    story = models.OneToOneField("NewsletterStory", on_delete=models.CASCADE, related_name="distribution_plan")
    internal_count = models.PositiveIntegerField(default=50)
    external_count = models.PositiveIntegerField(default=10)
    languages = models.JSONField(default=list)
    requires_owner_approval = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)

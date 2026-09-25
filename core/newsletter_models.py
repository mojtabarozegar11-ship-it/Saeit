import datetime
from django.db import models
from django.utils import timezone


class NewsletterSource(models.Model):
    KIND_CHOICES = (("company", "Company"), ("world", "World"), ("research", "Research"))
    publisher = models.CharField(max_length=300)
    title = models.CharField(max_length=500)
    url = models.URLField(unique=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="world")
    retrieved_at = models.DateTimeField(default=timezone.now)
    content_hash = models.CharField(max_length=128, blank=True, db_index=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ("-retrieved_at",)


class NewsletterStory(models.Model):
    TYPE_CHOICES = (("company", "Company Activity"), ("world", "World News"), ("report", "Company Report"))
    STATUS_CHOICES = (("draft", "Draft"), ("approved", "Approved"), ("scheduled", "Scheduled"), ("published", "Published"), ("rejected", "Rejected"))
    agent = models.ForeignKey("core.Agent", on_delete=models.PROTECT, related_name="newsletter_stories")
    source = models.ForeignKey(NewsletterSource, on_delete=models.PROTECT, null=True, blank=True, related_name="stories")
    story_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=500)
    slug = models.SlugField(max_length=180, unique=True)
    summary = models.TextField()
    body = models.TextField()
    author_name = models.CharField(max_length=200, default="مجتبی روزگار")
    event_date = models.DateField(null=True, blank=True)
    company_activity_kind = models.CharField(max_length=30, blank=True, choices=(("activity", "Company Activity"), ("visit", "CEO Visit"), ("directive", "CEO Directive")))
    manager_action = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    fingerprint = models.CharField(max_length=128, unique=True)
    source_fingerprint = models.CharField(max_length=128, blank=True, db_index=True)
    seo_keywords = models.JSONField(default=list)
    image = models.FileField(upload_to="newsletter/images/", blank=True, null=True)
    video = models.FileField(upload_to="newsletter/videos/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-published_at", "-created_at")
        indexes = [models.Index(fields=("story_type", "status", "published_at"))]


class NewsletterSubmission(models.Model):
    STATUS_CHOICES = (("queued", "Queued"), ("processing", "Processing"), ("drafted", "Draft Created"), ("rejected", "Rejected"))
    subject = models.CharField(max_length=500)
    body = models.TextField()
    image = models.FileField(upload_to="newsletter/submissions/images/", blank=True, null=True)
    video = models.FileField(upload_to="newsletter/submissions/videos/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    created_by = models.ForeignKey("auth.User", on_delete=models.PROTECT, related_name="newsletter_submissions")
    created_at = models.DateTimeField(auto_now_add=True)
    requested_publish_at = models.DateTimeField(null=True, blank=True)
    occasion_code = models.CharField(max_length=80, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    generated_story = models.OneToOneField("NewsletterStory", on_delete=models.SET_NULL, null=True, blank=True, related_name="source_submission")

    class Meta:
        ordering = ("-created_at",)


class NewsletterOccasion(models.Model):
    KIND_CHOICES = (("iranian", "Iranian"), ("shia", "Shia"), ("company", "Company Related"))
    code = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=250)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    date_rule = models.CharField(max_length=80, help_text="ISO date or annually maintained date rule")
    message_template = models.TextField()
    active = models.BooleanField(default=True)
    requires_owner_approval = models.BooleanField(default=True)

    class Meta:
        ordering = ("kind", "title")


class NewsletterPublication(models.Model):
    CHANNEL_CHOICES = (
        ("site", "Website"), ("instagram", "Instagram"), ("facebook", "Facebook"),
        ("youtube", "YouTube"), ("x", "X"), ("linkedin", "LinkedIn"),
        ("telegram", "Telegram"), ("eitaa", "Eitaa"), ("rubika", "Rubika"),
        ("bale", "Bale"),
    )
    STATUS_CHOICES = (("queued", "Queued"), ("published", "Published"), ("failed", "Failed"), ("blocked", "Blocked"))
    story = models.ForeignKey(NewsletterStory, on_delete=models.CASCADE, related_name="publications")
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    external_id = models.CharField(max_length=300, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("story", "channel"), name="unique_newsletter_story_channel")]
        ordering = ("-created_at",)


class NewsletterSchedule(models.Model):
    start_date = models.DateField(default=datetime.date(2019, 11, 16))
    company_news_daily = models.PositiveIntegerField(default=4)
    world_news_daily = models.PositiveIntegerField(default=4)
    reports_daily = models.PositiveIntegerField(default=4)
    company_daily_pattern = models.JSONField(default=list, blank=True)
    publication_requires_approval = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Newsletter Schedule"
        verbose_name_plural = "Newsletter Schedules"


class NewsletterAgentLink(models.Model):
    parent = models.ForeignKey("core.Agent", on_delete=models.CASCADE, related_name="newsletter_children")
    child = models.OneToOneField("core.Agent", on_delete=models.CASCADE, related_name="newsletter_parent")
    sequence = models.PositiveIntegerField(default=1)
    responsibility = models.TextField()

    class Meta:
        ordering = ("sequence",)
        constraints = [models.UniqueConstraint(fields=("parent", "sequence"), name="unique_newsletter_agent_sequence")]

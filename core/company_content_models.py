from django.db import models
from django.utils import timezone


class CompanyContentLink(models.Model):
    """Connect one published knowledge/news item to a real Company Portal page."""
    CONTENT_TYPES = (("newsletter", "Newsletter"), ("knowledge", "Knowledge"))
    RELATION_TYPES = (("primary", "Primary"), ("related", "Related"))
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    newsletter_story = models.ForeignKey("NewsletterStory", on_delete=models.CASCADE, null=True, blank=True, related_name="company_links")
    knowledge_article = models.ForeignKey("KnowledgeArticle", on_delete=models.CASCADE, null=True, blank=True, related_name="company_links")
    target_path = models.CharField(max_length=300, help_text="Must point to a real /company/ page or anchor.")
    relation = models.CharField(max_length=20, choices=RELATION_TYPES, default="related")
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("target_path", "content_type"))]

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.target_path.startswith("/company/"):
            raise ValidationError({"target_path": "Company links must start with /company/."})
        if self.content_type == "newsletter" and not self.newsletter_story_id:
            raise ValidationError({"newsletter_story": "Newsletter content requires a story."})
        if self.content_type == "knowledge" and not self.knowledge_article_id:
            raise ValidationError({"knowledge_article": "Knowledge content requires an article."})


class CompanyGalleryMedia(models.Model):
    MEDIA_TYPES = (("image", "Image"), ("video", "Video"))
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    image = models.FileField(upload_to="company/gallery/images/", blank=True, null=True)
    video = models.FileField(upload_to="company/gallery/videos/", blank=True, null=True)
    target_path = models.CharField(max_length=300, blank=True, help_text="Optional Company Portal page/anchor.")
    newsletter_story = models.ForeignKey("NewsletterStory", on_delete=models.SET_NULL, null=True, blank=True, related_name="gallery_media")
    project_label = models.CharField(max_length=200, blank=True)
    research_domain = models.CharField(max_length=200, blank=True)
    tags = models.JSONField(default=list, blank=True)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-published_at", "-created_at")
        indexes = [models.Index(fields=("media_type", "published", "published_at"))]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.target_path and not self.target_path.startswith("/company/"):
            raise ValidationError({"target_path": "Gallery Company links must start with /company/."})
        if self.media_type == "image" and not self.image:
            raise ValidationError({"image": "An image is required for image media."})
        if self.media_type == "video" and not self.video:
            raise ValidationError({"video": "A video is required for video media."})

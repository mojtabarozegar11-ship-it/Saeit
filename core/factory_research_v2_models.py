"""Source-job models for eventual integration into the deployed Django project.

NOTE: Django will not discover these models until imported from core.models.
"""
from django.db import models


class FactorySourceJob(models.Model):
    project = models.ForeignKey("core.ResearchProject", on_delete=models.CASCADE,
                                related_name="factory_source_jobs")
    url = models.URLField(max_length=1800)
    status = models.CharField(max_length=20, default="queued", db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    leased_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "url"],
                                    name="factory_v2_project_url_unique")
        ]


class FactoryEvidenceSnapshot(models.Model):
    source_job = models.OneToOneField("core.FactorySourceJob", on_delete=models.CASCADE,
                                     related_name="snapshot")
    sha256 = models.CharField(max_length=64)
    body = models.TextField()
    content_type = models.CharField(max_length=100)
    fetched_at = models.DateTimeField()
    verified_relevant = models.BooleanField(default=False)

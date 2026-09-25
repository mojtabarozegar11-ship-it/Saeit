from django.db import models


class CompanyInquiry(models.Model):
    KIND_CHOICES = (
        ("research", "همکاری پژوهشی"),
        ("technology", "فناوری و نوآوری"),
        ("project", "پروژه و توسعه"),
        ("commercial", "همکاری تجاری"),
        ("media", "رسانه و محتوا"),
    )
    STATUS_CHOICES = (("new", "جدید"), ("reviewing", "در حال بررسی"), ("approved", "تأیید اولیه"), ("closed", "بسته"))
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    name = models.CharField(max_length=200)
    organization = models.CharField(max_length=250, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True)
    subject = models.CharField(max_length=300)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    internal_note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "created_at")), models.Index(fields=("kind", "status"))]

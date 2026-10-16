from django.db import models

from .models import T


class FarnazService(T):
    title = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    summary = models.CharField(max_length=360)
    details = models.TextField(blank=True)
    image_url = models.URLField(blank=True)
    starting_price = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    price_currency = models.CharField(max_length=12, default="USD")
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Farnaz service"
        verbose_name_plural = "Farnaz services"

    def __str__(self):
        return self.title


class FarnazProject(T):
    title = models.CharField(max_length=180)
    discipline = models.CharField(max_length=100)
    summary = models.TextField()
    image_url = models.URLField(blank=True)
    is_concept = models.BooleanField(default=True)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Farnaz portfolio item"
        verbose_name_plural = "Farnaz portfolio"

    def __str__(self):
        return self.title


class FarnazOffer(T):
    class Kind(models.TextChoices):
        CONSULTATION = "consultation", "Consultation"
        DIGITAL = "digital", "Digital product"
        TRAINING = "training", "Training"
        SERVICE = "service", "Project service"

    title = models.CharField(max_length=180)
    kind = models.CharField(max_length=24, choices=Kind.choices)
    description = models.TextField()
    cover_url = models.URLField(blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=0, null=True, blank=True)
    currency = models.CharField(max_length=12, default="USD")
    checkout_enabled = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "Farnaz offer"
        verbose_name_plural = "Farnaz offers"

    def __str__(self):
        return self.title


class FarnazInquiry(T):
    class Category(models.TextChoices):
        DRAWING = "drawing", "Drafting and documentation"
        CAD = "cad", "CAD review and cleanup"
        BIM = "bim", "3D modelling and visualization"
        DIGITAL = "digital", "Digital files or products"
        TRAINING = "training", "Training"
        CONSULTING = "consulting", "Consultation and estimate"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUOTED = "quoted", "Estimate sent"
        CLOSED = "closed", "Closed"

    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40)
    email = models.EmailField(blank=True)
    category = models.CharField(max_length=24, choices=Category.choices)
    message = models.TextField(max_length=3000)
    consent = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.NEW)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Farnaz enquiry"
        verbose_name_plural = "Farnaz enquiries"

    def __str__(self):
        return f"{self.name} — {self.get_category_display()}"

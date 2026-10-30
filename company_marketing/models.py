"""Unit-scoped campaigns and publication workflow; zero automatic spending."""
import hashlib
import uuid
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


PLATFORMS = (
    ("bale", "بله"), ("eitaa", "ایتا"), ("rubika", "روبیکا"),
    ("telegram", "تلگرام"), ("soroush", "سروش پلاس"), ("gap", "گپ"),
    ("igap", "آی‌گپ"), ("instagram", "اینستاگرام"), ("facebook", "فیسبوک"),
    ("linkedin", "لینکدین"), ("youtube", "یوتیوب"), ("website", "وب‌سایت"),
)
AUTOMATED_PLATFORMS = frozenset(("bale", "rubika", "telegram"))


class Campaign(models.Model):
    unit = models.ForeignKey("enterprise_portal.BusinessUnit", on_delete=models.PROTECT)
    code = models.SlugField(max_length=64)
    title = models.CharField(max_length=240)
    objective = models.TextField()
    audience = models.CharField(max_length=240, blank=True)
    starts_on = models.DateField(default=timezone.localdate)
    ends_on = models.DateField(null=True, blank=True)
    budget_ceiling_irr = models.DecimalField(max_digits=20, decimal_places=0, default=0)
    status = models.CharField(max_length=12, choices=(
        ("draft", "برنامه‌ریزی"), ("active", "فعال"),
        ("paused", "متوقف"), ("closed", "مختومه"),
    ), default="draft")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "code"), name="zm_mkt_campaign_code")]
        ordering = ("-created_at",)
        permissions = [("manage_company_campaigns", "مدیریت کمپین‌های واحد سازمانی")]

    def clean(self):
        if self.ends_on and self.ends_on < self.starts_on:
            raise ValidationError({"ends_on": "تاریخ پایان پیش از شروع مجاز نیست."})
        if self.budget_ceiling_irr is None or self.budget_ceiling_irr < 0:
            raise ValidationError({"budget_ceiling_irr": "بودجه منفی مجاز نیست."})

    def save(self, *args, **kwargs):
        # Enforce the campaign lifecycle for all writers, including admin and
        # background jobs; closed campaigns must not be silently resurrected.
        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            transitions = {
                "draft": ("active", "closed"),
                "active": ("paused", "closed"),
                "paused": ("active", "closed"),
                "closed": (),
            }
            if self.status != previous.status and self.status not in transitions.get(previous.status, ()):
                raise ValidationError("تغییر وضعیت کمپین خارج از گردش‌کار مجاز است.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class ChannelAccount(models.Model):
    unit = models.ForeignKey("enterprise_portal.BusinessUnit", on_delete=models.PROTECT)
    platform = models.CharField(max_length=16, choices=PLATFORMS)
    title = models.CharField(max_length=180)
    destination = models.CharField(max_length=120, help_text="شناسه کانال متعلق به شرکت؛ بدون توکن")
    is_company_owned = models.BooleanField(default=False)
    ownership_evidence = models.CharField(max_length=255, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("unit", "platform", "destination"),
                                               name="zm_mkt_channel_destination")]
        ordering = ("platform", "title")

    def clean(self):
        if self.is_company_owned and (not self.ownership_evidence.strip() or not self.verified_at):
            raise ValidationError("مالکیت کانال باید با مرجع و زمان ثبت شود.")
        if not self.destination.strip():
            raise ValidationError({"destination": "شناسه مقصد ضروری است."})

    def save(self, *args, **kwargs):
        # A verified channel is an approved external destination. Re-pointing it
        # would silently redirect previously approved publications.
        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            if previous.is_company_owned and previous.verified_at and (
                self.unit_id, self.platform, self.destination, self.is_company_owned,
                self.ownership_evidence, self.verified_at
            ) != (
                previous.unit_id, previous.platform, previous.destination,
                previous.is_company_owned, previous.ownership_evidence, previous.verified_at
            ):
                raise ValidationError(
                    "هویت و مدرک کانال تأییدشده تغییر نمی‌کند؛ برای مقصد تازه حساب جدید بسازید."
                )
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return "%s — %s" % (self.get_platform_display(), self.title)


class Publication(models.Model):
    STATUS = (
        ("draft", "پیش‌نویس"), ("approved", "تأیید انتشار"),
        ("sending", "در حال ارسال"), ("accepted", "پذیرش سرویس‌دهنده"),
        ("blocked", "مسدود"), ("uncertain", "نیازمند بررسی"),
    )
    key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, related_name="publications")
    channel = models.ForeignKey(ChannelAccount, on_delete=models.PROTECT)
    title = models.CharField(max_length=220)
    content = models.TextField(max_length=4000)
    landing_url = models.URLField(blank=True)
    scheduled_at = models.DateTimeField(default=timezone.now)
    rights_reference = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="draft", editable=False)
    content_sha256 = models.CharField(max_length=64, blank=True, editable=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="marketing_publications_created")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    null=True, blank=True, related_name="marketing_publications_approved")
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    provider_reference = models.CharField(max_length=128, blank=True, editable=False)
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    attempts = models.PositiveSmallIntegerField(default=0, editable=False)
    error_code = models.CharField(max_length=48, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [models.Index(fields=("status", "scheduled_at"), name="zm_pub_schedule_idx")]
        permissions = [
            ("approve_publication", "تأیید انتشار تبلیغات"),
            ("dispatch_publication", "اجرای انتشار زمان‌بندی‌شده"),
        ]

    def payload_hash(self):
        value = "\x00".join((self.title, self.content, self.landing_url, self.rights_reference))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def clean(self):
        if not self.content or not self.content.strip():
            raise ValidationError({"content": "محتوای خالی مجاز نیست."})
        if self.campaign_id and self.channel_id and self.campaign.unit_id != self.channel.unit_id:
            raise ValidationError("کمپین و کانال باید متعلق به همان واحد باشند.")
        if self.status != "draft":
            if not (self.rights_reference.strip() and self.content_sha256 == self.payload_hash()):
                raise ValidationError("تأیید حقوق و هش نسخه منتشرشدنی معتبر نیست.")
        if self.status in ("approved", "sending", "accepted", "uncertain"):
            if not self.channel.is_company_owned or not self.channel.verified_at or not self.channel.active:
                raise ValidationError("مالکیت و دسترسی کانال تأیید نشده است.")

    def save(self, *args, **kwargs):
        if self.pk:
            prev = type(self).objects.get(pk=self.pk)
            if prev.status != "draft" and (
                self.title, self.content, self.landing_url, self.rights_reference,
                self.campaign_id, self.channel_id
            ) != (
                prev.title, prev.content, prev.landing_url, prev.rights_reference,
                prev.campaign_id, prev.channel_id
            ):
                raise ValidationError("محتوای تأییدشده تغییر نمی‌کند؛ نسخه جدید بسازید.")
        self.full_clean()
        return super().save(*args, **kwargs)


class PublicationEvent(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.PROTECT, related_name="events")
    code = models.CharField(max_length=48)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class Lead(models.Model):
    STAGES = (
        ("new", "سرنخ جدید"), ("contacted", "تماس انجام‌شده"),
        ("qualified", "واجد شرایط"), ("proposal", "پیشنهاد ارسال‌شده"),
        ("won", "فروش واقعی"), ("lost", "ناموفق"),
    )
    unit = models.ForeignKey("enterprise_portal.BusinessUnit", on_delete=models.PROTECT)
    campaign = models.ForeignKey(Campaign, on_delete=models.PROTECT, null=True, blank=True)
    contact = models.ForeignKey("company_messaging.Contact", on_delete=models.PROTECT)
    stage = models.CharField(max_length=16, choices=STAGES, default="new")
    source = models.CharField(max_length=120)
    estimated_value_irr = models.DecimalField(max_digits=20, decimal_places=0, default=0)
    verified_sale_irr = models.DecimalField(max_digits=20, decimal_places=0, default=0)
    sale_evidence_reference = models.CharField(max_length=255, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        if self.contact_id and self.unit_id and self.contact.unit_id != self.unit_id:
            raise ValidationError("مخاطب متعلق به واحد دیگر است.")
        if self.campaign_id and self.unit_id and self.campaign.unit_id != self.unit_id:
            raise ValidationError("کمپین متعلق به واحد دیگر است.")
        if min(self.estimated_value_irr or 0, self.verified_sale_irr or 0) < 0:
            raise ValidationError("مقادیر منفی مجاز نیست.")
        if self.stage == "won" and (not self.sale_evidence_reference.strip()
                                    or self.verified_sale_irr <= 0):
            raise ValidationError("فروش واقعی بدون سند و مبلغ تأییدشده ثبت نمی‌شود.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class PerformanceMetric(models.Model):
    publication = models.ForeignKey(Publication, on_delete=models.PROTECT, related_name="metrics")
    recorded_on = models.DateField(default=timezone.localdate)
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    leads = models.PositiveIntegerField(default=0)
    cost_irr = models.DecimalField(max_digits=20, decimal_places=0, default=0)
    evidence_reference = models.CharField(max_length=255)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-recorded_on",)

    def clean(self):
        if self.recorded_on and self.recorded_on > timezone.localdate():
            raise ValidationError({"recorded_on": "آمار عملکرد برای تاریخ آینده قابل تأیید نیست."})
        if self.cost_irr is None or self.cost_irr < 0:
            raise ValidationError("هزینه منفی مجاز نیست.")
        if not self.evidence_reference.strip():
            raise ValidationError("منبع مستقل آمار ضروری است.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

"""Private, multi-unit communication records. No automatic external sends on save."""
import uuid
from django.utils.crypto import salted_hmac
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Contact(models.Model):
    unit = models.ForeignKey("enterprise_portal.BusinessUnit", on_delete=models.PROTECT, related_name="message_contacts")
    name = models.CharField(max_length=180)
    email = models.EmailField(blank=True)
    phone_e164 = models.CharField(max_length=20, blank=True)
    telegram_chat_id = models.CharField(max_length=80, blank=True)
    bale_chat_id = models.CharField(max_length=80, blank=True)
    eitaa_chat_id = models.CharField(max_length=80, blank=True)
    rubika_chat_id = models.CharField(max_length=80, blank=True)
    active = models.BooleanField(default=True)
    email_consent_at = models.DateTimeField(null=True, blank=True)
    sms_consent_at = models.DateTimeField(null=True, blank=True)
    telegram_consent_at = models.DateTimeField(null=True, blank=True)
    bale_consent_at = models.DateTimeField(null=True, blank=True)
    eitaa_consent_at = models.DateTimeField(null=True, blank=True)
    rubika_consent_at = models.DateTimeField(null=True, blank=True)
    whatsapp_consent_at = models.DateTimeField(null=True, blank=True)
    consent_evidence = models.CharField(max_length=255, blank=True)
    suppressed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name", "pk")
        permissions = [("manage_company_contacts", "مدیریت دفترچه مخاطبان شرکت")]

    def __str__(self):
        return self.name

    def clean(self):
        if self.phone_e164 and (
            not self.phone_e164.startswith("+") or not self.phone_e164[1:].isdigit()
            or not 8 <= len(self.phone_e164) <= 16
        ):
            raise ValidationError({"phone_e164": "شماره باید با کد کشور و قالب E.164 باشد."})
        consents = (self.email_consent_at, self.sms_consent_at,
                    self.telegram_consent_at, self.bale_consent_at,
                    self.eitaa_consent_at, self.rubika_consent_at, self.whatsapp_consent_at)
        if any(value and value > timezone.now() for value in consents):
            raise ValidationError({"consent_evidence": "رضایت با تاریخ آینده معتبر نیست."})
        if any(consents) and not self.consent_evidence.strip():
            raise ValidationError({"consent_evidence": "مرجع قابل پیگیری رضایت ضروری است."})

    def save(self, *args, **kwargs):
        # Direct ORM saves must not persist invented or future-dated opt-ins.
        # QuerySet.update/bulk_update still bypass model hooks: dispatch
        # independently revalidates the locked consent snapshot.
        self.full_clean()
        return super().save(*args, **kwargs)


class Message(models.Model):
    CHANNELS = (
        ("internal", "داخلی"), ("email", "ایمیل"), ("sms", "پیامک"),
        ("telegram", "تلگرام"), ("bale", "بله"),
        ("eitaa", "ایتا"), ("rubika", "روبیکا"), ("whatsapp", "واتساپ"),
    )
    STATUSES = (
        ("queued", "در صف"), ("internal", "دریافت داخلی"),
        ("sending", "در حال ارسال"), ("accepted", "پذیرش سرویس‌دهنده"),
        ("blocked", "مسدود"), ("uncertain", "نیازمند بررسی"),
    )
    key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    unit = models.ForeignKey("enterprise_portal.BusinessUnit", on_delete=models.PROTECT)
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="company_messages_sent")
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.PROTECT)
    recipient_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                       on_delete=models.PROTECT, related_name="company_messages_received")
    channel = models.CharField(max_length=12, choices=CHANNELS)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(max_length=4096)
    status = models.CharField(max_length=12, choices=STATUSES, default="queued", editable=False)
    scheduled_at = models.DateTimeField(default=timezone.now)
    accepted_at = models.DateTimeField(null=True, blank=True, editable=False)
    read_at = models.DateTimeField(null=True, blank=True, editable=False)
    attempts = models.PositiveSmallIntegerField(default=0, editable=False)
    external_reference = models.CharField(max_length=128, blank=True, editable=False)
    recipient_fingerprint = models.CharField(max_length=64, blank=True, default="", editable=False)
    error_code = models.CharField(max_length=48, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "scheduled_at"), name="zm_msg_dispatch_idx"),
            models.Index(fields=("unit", "created_at"), name="zm_msg_unit_idx"),
        ]
        permissions = [
            ("dispatch_company_message", "اجرای ارسال پیام از صف"),
            ("view_company_message_audit", "مشاهده رویدادهای پیام"),
        ]

    def __str__(self):
        return "%s / %s" % (self.pk, self.get_channel_display())

    def destination_fingerprint(self):
        """Private keyed fingerprint of the consent and destination at queue time."""
        if self.channel == "internal" or not self.contact_id:
            return ""
        contact = self.contact
        destination = {
            "email": contact.email, "sms": contact.phone_e164,
            "telegram": contact.telegram_chat_id, "bale": contact.bale_chat_id,
            "eitaa": contact.eitaa_chat_id, "rubika": contact.rubika_chat_id,
            "whatsapp": contact.phone_e164,
        }.get(self.channel, "")
        consent = getattr(contact, self.channel + "_consent_at", None)
        payload = "\x00".join((
            self.channel, destination or "",
            consent.isoformat() if consent else "",
            contact.consent_evidence or "",
        ))
        return salted_hmac("company_messaging.recipient_lock", payload,
                           algorithm="sha256").hexdigest()

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            locked = ("unit_id", "sender_id", "contact_id", "recipient_user_id",
                      "channel", "subject", "body", "scheduled_at", "recipient_fingerprint")
            if any(getattr(self, field) != getattr(previous, field) for field in locked):
                raise ValidationError("پیام در صف ثابت است؛ برای محتوا یا گیرنده جدید پیام تازه بسازید.")
        return super().save(*args, **kwargs)

    def clean(self):
        if not self.body or not self.body.strip():
            raise ValidationError({"body": "متن پیام خالی است."})
        from ecosystem_hub.access import can_view_unit
        if self.sender_id and not can_view_unit(self.sender, self.unit):
            raise ValidationError("فرستنده مجوز واحد سازمانی ندارد.")
        if self.channel == "internal":
            if not self.recipient_user_id or self.contact_id:
                raise ValidationError("پیام داخلی باید گیرنده کارمند داشته باشد.")
            if not self.recipient_user.is_active or not self.recipient_user.is_staff:
                raise ValidationError("گیرنده داخلی باید کارمند فعال باشد.")
            if not can_view_unit(self.recipient_user, self.unit):
                raise ValidationError("گیرنده عضو مجاز این واحد سازمانی نیست.")
        else:
            if not self.contact_id or self.recipient_user_id:
                raise ValidationError("پیام بیرونی باید مخاطب ثبت‌شده داشته باشد.")
            contact = self.contact
            if contact.unit_id != self.unit_id or not contact.active or contact.suppressed:
                raise ValidationError("مخاطب غیرفعال، مسدود یا متعلق به واحد دیگر است.")
            consent = getattr(contact, self.channel + "_consent_at", None)
            address = {
                "email": contact.email, "sms": contact.phone_e164,
                "telegram": contact.telegram_chat_id, "bale": contact.bale_chat_id,
                "eitaa": contact.eitaa_chat_id, "rubika": contact.rubika_chat_id,
                "whatsapp": contact.phone_e164,
            }.get(self.channel)
            if not consent or not contact.consent_evidence or not address:
                raise ValidationError("نشانی و رضایت مستند این کانال لازم است.")
            # A future-dated opt-in is not consent effective at queue/dispatch time.
            # This guard also covers contacts saved through direct ORM writes.
            if consent > timezone.now():
                raise ValidationError("رضایت این کانال هنوز معتبر نشده است.")
            if self.pk and self.status in ("queued", "sending"):
                if not self.recipient_fingerprint or self.recipient_fingerprint != self.destination_fingerprint():
                    raise ValidationError("نشانی یا رضایت مخاطب پس از ثبت صف تغییر کرده است.")


class MessageEvent(models.Model):
    message = models.ForeignKey(Message, on_delete=models.PROTECT, related_name="events")
    code = models.CharField(max_length=48)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

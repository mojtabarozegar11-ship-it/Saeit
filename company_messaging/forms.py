from django import forms
from django.db.models import Q
from enterprise_portal.forms import colleagues
from enterprise_portal.models import BusinessUnit
from ecosystem_hub.access import user_units
from .models import Contact, Message


class ComposeForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ("unit", "channel", "contact", "recipient_user", "subject", "body", "scheduled_at")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 7, "maxlength": 4096}),
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        units = user_units(user)
        self.fields["unit"].queryset = units
        self.fields["contact"].queryset = Contact.objects.filter(unit__in=units, active=True, suppressed=False)
        self.fields["recipient_user"].queryset = colleagues(user)
        self.fields["contact"].required = False
        self.fields["recipient_user"].required = False
        self.fields["scheduled_at"].required = False
        self.fields["scheduled_at"].initial = None

    def clean(self):
        data = super().clean()
        if data.get("channel") == "internal":
            if not data.get("recipient_user") or data.get("contact"):
                raise forms.ValidationError("برای پیام داخلی فقط کارمند گیرنده را انتخاب کنید.")
            colleague = data["recipient_user"]
            unit = data.get("unit")
            if unit and not (colleague.is_superuser or colleague.ecosystem_memberships.filter(
                unit=unit, active=True).exists()):
                raise forms.ValidationError("کارمند باید عضو واحد سازمانی انتخابی باشد.")
        else:
            if not data.get("contact") or data.get("recipient_user"):
                raise forms.ValidationError("برای پیام خارجی فقط مخاطب دفترچه را انتخاب کنید.")
            if data.get("contact") and data.get("unit") and data["contact"].unit_id != data["unit"].pk:
                raise forms.ValidationError("مخاطب باید متعلق به همین واحد باشد.")
        return data



class ContactForm(forms.ModelForm):
    """Unit-scoped recipient record; consent is never inferred from an address."""

    class Meta:
        model = Contact
        fields = (
            "unit", "name", "email", "phone_e164",
            "telegram_chat_id", "bale_chat_id", "eitaa_chat_id", "rubika_chat_id",
            "email_consent_at", "sms_consent_at", "telegram_consent_at",
            "bale_consent_at", "eitaa_consent_at", "rubika_consent_at",
            "whatsapp_consent_at", "consent_evidence", "active", "suppressed",
        )
        labels = {
            "unit": "واحد سازمانی", "name": "نام مخاطب", "email": "ایمیل",
            "phone_e164": "شماره همراه با کد کشور (+98...)",
            "telegram_chat_id": "شناسه گفت‌وگوی تلگرام", "bale_chat_id": "شناسه بله",
            "eitaa_chat_id": "شناسه ایتا", "rubika_chat_id": "شناسه روبیکا",
            "email_consent_at": "تاریخ رضایت ایمیل", "sms_consent_at": "تاریخ رضایت پیامک",
            "telegram_consent_at": "تاریخ رضایت تلگرام", "bale_consent_at": "تاریخ رضایت بله",
            "eitaa_consent_at": "تاریخ رضایت ایتا", "rubika_consent_at": "تاریخ رضایت روبیکا",
            "whatsapp_consent_at": "تاریخ رضایت واتساپ",
            "consent_evidence": "مرجع قابل پیگیری رضایت",
            "active": "مخاطب فعال است", "suppressed": "ارسال به مخاطب مسدود است",
        }
        widgets = {
            field: forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"})
            for field in (
                "email_consent_at", "sms_consent_at", "telegram_consent_at",
                "bale_consent_at", "eitaa_consent_at", "rubika_consent_at",
                "whatsapp_consent_at",
            )
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit"].queryset = user_units(user) if user else BusinessUnit.objects.none()
        if self.instance.pk:
            # No moving an existing consent record to another business unit.
            self.fields["unit"].disabled = True

    def clean(self):
        data = super().clean()
        destinations = (
            "email", "phone_e164", "telegram_chat_id", "bale_chat_id",
            "eitaa_chat_id", "rubika_chat_id",
        )
        if not any(str(data.get(field) or "").strip() for field in destinations):
            raise forms.ValidationError("دست‌کم یک نشانی تماس معتبر لازم است.")
        return data

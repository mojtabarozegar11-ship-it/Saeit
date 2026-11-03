from django import forms
from django.db.models import Q
from enterprise_portal.forms import colleagues
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

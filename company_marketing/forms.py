from django import forms
from ecosystem_hub.access import user_units
from .models import Campaign, ChannelAccount, Publication, Lead, PerformanceMetric


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ("unit", "code", "title", "objective", "audience",
                  "starts_on", "ends_on", "budget_ceiling_irr")
        widgets = {
            "objective": forms.Textarea(attrs={"rows": 4}),
            "starts_on": forms.DateInput(attrs={"type": "date"}),
            "ends_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit"].queryset = user_units(user)


class PublicationForm(forms.ModelForm):
    class Meta:
        model = Publication
        fields = ("campaign", "channel", "title", "content", "landing_url",
                  "scheduled_at", "rights_reference")
        widgets = {
            "content": forms.Textarea(attrs={"rows": 7, "maxlength": 4000}),
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        units = user_units(user)
        self.fields["campaign"].queryset = Campaign.objects.filter(unit__in=units).exclude(status="closed")
        self.fields["channel"].queryset = ChannelAccount.objects.filter(unit__in=units, active=True)
        self.fields["scheduled_at"].required = False

    def clean(self):
        cleaned = super().clean()
        campaign, channel = cleaned.get("campaign"), cleaned.get("channel")
        if campaign and channel and campaign.unit_id != channel.unit_id:
            raise forms.ValidationError("کمپین و کانال باید متعلق به یک واحد باشند.")
        return cleaned


class ChannelAccountForm(forms.ModelForm):
    class Meta:
        model = ChannelAccount
        fields = ("unit", "platform", "title", "destination", "active")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unit"].queryset = user_units(user)


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ("unit", "campaign", "contact", "stage", "source",
                  "estimated_value_irr", "verified_sale_irr", "sale_evidence_reference")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from company_messaging.models import Contact
        units = user_units(user)
        self.fields["unit"].queryset = units
        self.fields["campaign"].queryset = Campaign.objects.filter(unit__in=units)
        self.fields["contact"].queryset = Contact.objects.filter(unit__in=units)

    def clean(self):
        data = super().clean()
        unit, contact, campaign = data.get("unit"), data.get("contact"), data.get("campaign")
        if unit and ((contact and contact.unit_id != unit.pk)
                     or (campaign and campaign.unit_id != unit.pk)):
            raise forms.ValidationError("سرنخ، مخاطب و کمپین باید متعلق به یک واحد باشند.")
        return data


class PerformanceMetricForm(forms.ModelForm):
    class Meta:
        model = PerformanceMetric
        fields = ("publication", "recorded_on", "impressions", "clicks", "leads",
                  "cost_irr", "evidence_reference")
        widgets = {"recorded_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["publication"].queryset = Publication.objects.filter(
            campaign__unit__in=user_units(user))

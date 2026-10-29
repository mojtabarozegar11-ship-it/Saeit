from django import forms
from ecosystem_hub.access import user_units
from .models import Campaign, ChannelAccount, Publication


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

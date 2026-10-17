from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import WorkTask, OfficeLetter, BusinessUnit
from .security import login_is_blocked, register_failed_login, clear_login_failures


def has_office_access(user):
    return bool(
        user.is_authenticated and user.is_active and user.is_staff and
        (user.is_superuser or user.has_perm("enterprise_portal.view_businessunit"))
    )


class CompanyAuthenticationForm(AuthenticationForm):
    """Only authorized Django staff can establish a session in this private suite."""
    username = forms.CharField(
        label="نام کاربری",
        widget=forms.TextInput(attrs={
            "autocomplete": "username", "autocapitalize": "none",
            "autofocus": True, "placeholder": "نام کاربری",
        }),
    )
    password = forms.CharField(
        label="رمز عبور", strip=False,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "current-password", "placeholder": "رمز عبور",
        }),
    )

    def clean(self):
        identifier = self.cleaned_data.get("username", "").strip()
        # Identical error wording for wrong passwords, unauthorized accounts
        # and rate-limited combinations avoids user-account enumeration.
        if identifier and login_is_blocked(self.request, identifier):
            raise self.get_invalid_login_error()
        try:
            result = super().clean()
        except ValidationError:
            if identifier:
                register_failed_login(self.request, identifier)
            raise
        if identifier:
            clear_login_failures(self.request, identifier)
        return result

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not has_office_access(user):
            raise self.get_invalid_login_error()


from django.db.models import Q
from ecosystem_hub.access import user_units


def colleagues(user):
    """Only active colleagues in a shared business unit, plus the organization owner."""
    users = get_user_model().objects.filter(is_active=True, is_staff=True)
    if user is None or not user.is_authenticated:
        return users.none()
    if user.is_superuser:
        return users
    return users.filter(
        Q(pk=user.pk) | Q(is_superuser=True) |
        Q(ecosystem_memberships__unit__in=user_units(user),
          ecosystem_memberships__active=True)
    ).distinct()


class TaskForm(forms.ModelForm):
    class Meta:
        model = WorkTask
        fields = ("title", "description", "unit", "assigned_to", "priority", "due_on")
        widgets = {
            "due_on": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["assigned_to"].queryset = colleagues(user)
        if not (user and user.is_authenticated and user.is_superuser):
            self.fields["unit"].queryset = user_units(user) if user else BusinessUnit.objects.none()
            self.fields["unit"].required = True

    def clean(self):
        cleaned = super().clean()
        unit, assignee = cleaned.get("unit"), cleaned.get("assigned_to")
        if self.user and self.user.is_authenticated and self.user.is_superuser:
            return cleaned
        if not unit:
            self.add_error("unit", "ثبت وظیفه بدون تعیین واحد سازمانی مجاز نیست.")
        elif assignee and not (assignee.is_superuser or assignee.pk == self.user.pk or
                              assignee.ecosystem_memberships.filter(unit=unit, active=True).exists()):
            self.add_error("assigned_to", "مسئول کار باید عضو فعال همین واحد تجاری باشد.")
        return cleaned


class LetterForm(forms.ModelForm):
    class Meta:
        model = OfficeLetter
        fields = ("number", "subject", "direction", "body", "classification",
                  "sent_on", "recipient", "assigned_to")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 6}),
            "sent_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = colleagues(user)

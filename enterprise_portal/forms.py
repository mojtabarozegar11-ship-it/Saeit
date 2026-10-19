from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from .models import WorkTask, OfficeLetter
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


class TaskForm(forms.ModelForm):
    class Meta:
        model = WorkTask
        fields = ("title", "description", "unit", "assigned_to",
                  "priority", "due_on")
        widgets = {
            "due_on": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model = get_user_model()
        self.fields["assigned_to"].queryset = model.objects.filter(is_active=True, is_staff=True)


class LetterForm(forms.ModelForm):
    class Meta:
        model = OfficeLetter
        fields = ("number", "subject", "direction", "body", "classification",
                  "sent_on", "recipient", "assigned_to")
        widgets = {
            "body": forms.Textarea(attrs={"rows": 6}),
            "sent_on": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = get_user_model().objects.filter(
            is_active=True, is_staff=True,
        )

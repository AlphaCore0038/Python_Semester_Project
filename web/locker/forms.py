"""Django form validation for the web client (client-side input checks;
FastAPI re-validates everything authoritatively)."""
import re

from django import forms
from django.core.validators import validate_email

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


class RegisterForm(forms.Form):
    email = forms.EmailField(
        max_length=255,
        validators=[validate_email],
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password = forms.CharField(
        min_length=8,
        max_length=128,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )


class LoginForm(forms.Form):
    email = forms.EmailField(
        max_length=255,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    password = forms.CharField(
        max_length=128,
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class RenameForm(forms.Form):
    """Matches the FastAPI filename rule: 1-255 chars, no path separators
    or control characters. The API rejects (never rewrites) bad names."""

    filename = forms.CharField(min_length=1, max_length=255, strip=False)

    def clean_filename(self):
        name = self.cleaned_data["filename"]
        if any(sep in name for sep in ("/", "\\")):
            raise forms.ValidationError("File names cannot contain path separators.")
        if _CONTROL_CHARS.search(name):
            raise forms.ValidationError("File names cannot contain control characters.")
        if name.strip(". ") == "":
            raise forms.ValidationError("Enter a valid file name.")
        return name

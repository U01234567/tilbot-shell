"""Sign-up and sign-in forms. The browser checks them first; these checks are the ones that count."""

from django import forms
from django.conf import settings

from accounts.codes import LENGTH, normalize

STUDY = settings.STUDY  # read once at import; a test that overrides settings.STUDY doesn't reach these forms


class SignUpForm(forms.Form):
    """Age and gender, limited by project/project.toml."""

    age = forms.IntegerField(label=STUDY.texts["age"], min_value=STUDY.age_min, max_value=STUDY.age_max)
    gender = forms.ChoiceField(label=STUDY.texts["gender"], choices=[(gender, gender) for gender in STUDY.genders])


class SignInForm(forms.Form):
    code = forms.CharField(label=STUDY.texts["your_id"], min_length=LENGTH, max_length=LENGTH)

    def clean_code(self) -> str:
        return normalize(self.cleaned_data["code"])

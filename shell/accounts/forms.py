"""Sign-up and sign-in forms. The browser checks them first; these checks are the ones that count."""

from django import forms
from django.conf import settings

from accounts.codes import LENGTH, normalize


class SignUpForm(forms.Form):
    """Age and gender, limited by /project/project.toml."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        study = settings.STUDY
        self.fields["age"] = forms.IntegerField(
            label=study.texts["age"], min_value=study.age_min, max_value=study.age_max
        )
        self.fields["gender"] = forms.ChoiceField(
            label=study.texts["gender"], choices=[(gender, gender) for gender in study.genders]
        )


class SignInForm(forms.Form):
    code = forms.CharField(min_length=LENGTH, max_length=LENGTH)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["code"].label = settings.STUDY.texts["your_id"]

    def clean_code(self) -> str:
        return normalize(self.cleaned_data["code"])

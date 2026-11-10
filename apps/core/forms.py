from django import forms

from .models import CustomerProfile


class ProfileForm(forms.ModelForm):
    remove_avatar = forms.BooleanField(label="Удалить аватар", required=False)

    class Meta:
        model = CustomerProfile
        fields = ["first_name", "gender", "avatar"]
        widgets = {
            "first_name": forms.TextInput(
                attrs={"class": "contacts__form_iunput", "placeholder": "Введите имя"}
            ),
            "avatar": forms.FileInput(attrs={"class": "profile__avatar_input"}),
        }

    def clean_first_name(self):
        return (self.cleaned_data.get("first_name") or "").strip()

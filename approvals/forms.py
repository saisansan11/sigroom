from django import forms
from django.contrib.auth import get_user_model

from bookings.forms import BuddhistDateField

from .services import create_delegation


class DelegationForm(forms.Form):
    delegate = forms.ModelChoiceField(label="ผู้รักษาการ", queryset=get_user_model().objects.none())
    start_date = BuddhistDateField(label="ตั้งแต่", widget=forms.TextInput(attrs={"placeholder": "25/08/2569"}))
    end_date = BuddhistDateField(label="ถึง", widget=forms.TextInput(attrs={"placeholder": "29/08/2569"}))

    def __init__(self, *args, delegator, **kwargs):
        super().__init__(*args, **kwargs)
        self.delegator = delegator
        self.fields["delegate"].queryset = (
            get_user_model().objects.filter(is_active=True).exclude(pk=delegator.pk).order_by("rank", "first_name", "username")
        )

    def save(self):
        return create_delegation(
            self.delegator,
            self.cleaned_data["delegate"],
            self.cleaned_data["start_date"],
            self.cleaned_data["end_date"],
        )

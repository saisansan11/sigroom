from datetime import datetime, timedelta

from django import forms
from django.utils import timezone

from bookings.forms import BuddhistDateField, time_choices


class ResourceOutageForm(forms.Form):
    start_date = BuddhistDateField(label="วันที่เริ่ม", widget=forms.TextInput(attrs={"placeholder": "26/08/2569"}))
    start_time = forms.TimeField(label="เวลาเริ่ม", widget=forms.Select(choices=time_choices()), input_formats=["%H:%M"])
    end_date = BuddhistDateField(label="วันที่สิ้นสุด", widget=forms.TextInput(attrs={"placeholder": "30/08/2569"}))
    end_time = forms.TimeField(label="เวลาสิ้นสุด", widget=forms.Select(choices=time_choices()), input_formats=["%H:%M"])
    reason = forms.CharField(
        label="เหตุผล",
        max_length=200,
        widget=forms.TextInput(attrs={"list": "outage-reasons", "placeholder": "เลือกเหตุผลที่เคยใช้หรือพิมพ์เอง"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            tomorrow = timezone.localdate() + timedelta(days=1)
            self.initial.update(
                {"start_date": tomorrow, "start_time": "08:00", "end_date": tomorrow, "end_time": "17:00"}
            )

    def clean(self):
        cleaned = super().clean()
        if all(cleaned.get(name) for name in ("start_date", "start_time", "end_date", "end_time")):
            zone = timezone.get_current_timezone()
            cleaned["start_at"] = timezone.make_aware(
                datetime.combine(cleaned["start_date"], cleaned["start_time"]), zone
            )
            cleaned["end_at"] = timezone.make_aware(
                datetime.combine(cleaned["end_date"], cleaned["end_time"]), zone
            )
            if cleaned["end_at"] <= cleaned["start_at"]:
                raise forms.ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม")
        return cleaned

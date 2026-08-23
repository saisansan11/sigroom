from datetime import date, datetime, time

from django import forms
from django.utils import timezone

from accounts.models import Unit
from resources.models import Resource

from .models import Booking
from .services import frequent_values


class BuddhistDateField(forms.DateField):
    """รับวันที่แบบ 24/08/2569 และ ISO จากปฏิทิน แล้วแปลงเป็น ค.ศ."""

    default_error_messages = {"invalid": "กรุณาระบุวันที่รูปแบบ วัน/เดือน/ปี พ.ศ."}

    def to_python(self, value):
        if value in self.empty_values:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()
        try:
            if "/" in text:
                day, month, year = (int(part) for part in text.split("/"))
                if year >= 2400:
                    year -= 543
                return date(year, month, day)
            return date.fromisoformat(text)
        except (TypeError, ValueError):
            raise forms.ValidationError(self.error_messages["invalid"], code="invalid")

    def prepare_value(self, value):
        parsed = super().prepare_value(value)
        if isinstance(parsed, datetime):
            parsed = parsed.date()
        if isinstance(parsed, date):
            return f"{parsed.day:02d}/{parsed.month:02d}/{parsed.year + 543}"
        return parsed


def time_choices():
    choices = []
    for hour in range(7, 22):
        for minute in (0, 15, 30, 45):
            if hour == 21 and minute:
                continue
            value = f"{hour:02d}:{minute:02d}"
            choices.append((value, value))
    return choices


def _unit_ids_with_children(unit: Unit | None) -> set[int]:
    if not unit:
        return set()
    result = {unit.pk}
    queue = [unit.pk]
    while queue:
        children = list(Unit.objects.filter(parent_id__in=queue).values_list("pk", flat=True))
        result.update(children)
        queue = children
    return result


class BookingForm(forms.ModelForm):
    date = BuddhistDateField(label="วันที่", widget=forms.TextInput(attrs={"placeholder": "24/08/2569"}))
    start_time = forms.TimeField(label="เริ่ม", widget=forms.Select(choices=time_choices()), input_formats=["%H:%M"])
    end_time = forms.TimeField(label="สิ้นสุด", widget=forms.Select(choices=time_choices()), input_formats=["%H:%M"])
    fixed_equipment_choices = forms.MultipleChoiceField(
        label="อุปกรณ์ประจำห้องที่ต้องใช้",
        required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=(),
    )
    fixed_equipment_extra = forms.CharField(
        label="อุปกรณ์ประจำห้องเพิ่มเติม",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "พิมพ์เพิ่มเติม (ถ้ามี)"}),
    )

    class Meta:
        model = Booking
        fields = [
            "title", "purpose", "unit", "responsible_name", "responsible_phone", "attendees",
            "attendee_level", "layout", "equipment", "has_external_attendees", "external_attendees_note",
            "visibility", "note",
        ]
        widgets = {
            "equipment": forms.CheckboxSelectMultiple,
            "has_external_attendees": forms.RadioSelect(choices=((False, "ไม่มี"), (True, "มี"))),
            "visibility": forms.RadioSelect,
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user, room: Resource, allowed_fields: set[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.room = room
        self.fields["equipment"].queryset = Resource.objects.filter(
            resource_type=Resource.Type.EQUIPMENT,
            status=Resource.Status.ACTIVE,
        )
        if user.is_superuser:
            self.fields["unit"].queryset = Unit.objects.filter(is_active=True)
        else:
            self.fields["unit"].queryset = Unit.objects.filter(pk__in=_unit_ids_with_children(user.unit), is_active=True)
            if not self.instance.pk and user.unit_id:
                self.initial.setdefault("unit", user.unit_id)

        fixed_items = [line.strip() for line in room.fixed_equipment.splitlines() if line.strip()]
        self.fields["fixed_equipment_choices"].choices = [(item, item) for item in fixed_items]
        if self.instance.pk:
            local_start = timezone.localtime(self.instance.start_at)
            local_end = timezone.localtime(self.instance.end_at)
            self.initial.setdefault("date", local_start.date())
            self.initial.setdefault("start_time", local_start.strftime("%H:%M"))
            self.initial.setdefault("end_time", local_end.strftime("%H:%M"))
            selected = [line.strip() for line in self.instance.fixed_equipment_needed.splitlines() if line.strip()]
            self.initial.setdefault("fixed_equipment_choices", [item for item in selected if item in fixed_items])
            self.initial.setdefault("fixed_equipment_extra", "\n".join(item for item in selected if item not in fixed_items))

        datalist_fields = ("title", "responsible_name", "responsible_phone", "attendee_level", "layout")
        unit = self.instance.unit if self.instance.pk else getattr(user, "unit", None)
        self.datalists = {name: frequent_values(unit, name) for name in datalist_fields}
        for name in datalist_fields:
            self.fields[name].widget.attrs["list"] = f"frequent-{name}"
        layouts = [line.strip() for line in room.layouts.splitlines() if line.strip()]
        self.datalists["layout"] = list(dict.fromkeys([*layouts, *self.datalists["layout"]]))

        if allowed_fields is not None:
            keep = set(allowed_fields)
            if "fixed_equipment_needed" in keep:
                keep.update({"fixed_equipment_choices", "fixed_equipment_extra"})
            for name in list(self.fields):
                if name not in keep:
                    self.fields.pop(name)
        self.order_fields(
            [
                "date", "start_time", "end_time", "title", "purpose", "unit", "responsible_name",
                "responsible_phone", "attendees", "attendee_level", "layout", "fixed_equipment_choices",
                "fixed_equipment_extra", "equipment", "has_external_attendees", "external_attendees_note",
                "visibility", "note",
            ]
        )

    def clean(self):
        cleaned = super().clean()
        if {"date", "start_time", "end_time"}.issubset(self.fields):
            booking_date = cleaned.get("date")
            start_time = cleaned.get("start_time")
            end_time = cleaned.get("end_time")
            if booking_date and start_time and end_time:
                zone = timezone.get_current_timezone()
                cleaned["start_at"] = timezone.make_aware(datetime.combine(booking_date, start_time), zone)
                cleaned["end_at"] = timezone.make_aware(datetime.combine(booking_date, end_time), zone)
                if cleaned["end_at"] <= cleaned["start_at"]:
                    raise forms.ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม")
        if cleaned.get("has_external_attendees") and not cleaned.get("external_attendees_note"):
            self.add_error("external_attendees_note", "กรุณาระบุจำนวนหรือหน่วยของผู้เข้าร่วมภายนอก")
        if cleaned.get("visibility") == Booking.Visibility.SENSITIVE and not self.user.is_infosec_officer:
            self.add_error("visibility", "เฉพาะเจ้าหน้าที่ความมั่นคงสารสนเทศที่กำหนดกิจกรรมอ่อนไหวได้")
        return cleaned

    def save(self, commit=True):
        booking = super().save(commit=False)
        booking.room = self.room
        if "start_at" in self.cleaned_data:
            booking.start_at = self.cleaned_data["start_at"]
            booking.end_at = self.cleaned_data["end_at"]
        if "fixed_equipment_choices" in self.cleaned_data:
            values = list(self.cleaned_data.get("fixed_equipment_choices", []))
            extra = self.cleaned_data.get("fixed_equipment_extra", "").strip()
            if extra:
                values.extend(line.strip() for line in extra.splitlines() if line.strip())
            booking.fixed_equipment_needed = "\n".join(dict.fromkeys(values))
        if commit:
            booking.save()
            self.save_m2m()
        return booking

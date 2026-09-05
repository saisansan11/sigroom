from datetime import date, datetime, time

from django import forms
from django.utils import timezone

from accounts.models import Unit
from resources.models import Resource

from .models import Booking, BookingSeries
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
    is_series = forms.BooleanField(label="จองเป็นชุด", required=False)
    series_freq = forms.ChoiceField(
        label="รูปแบบชุด",
        required=False,
        choices=BookingSeries.Frequency.choices,
        initial=BookingSeries.Frequency.WEEKLY,
    )
    series_weekdays = forms.MultipleChoiceField(
        label="วันในสัปดาห์",
        required=False,
        choices=((0, "จ"), (1, "อ"), (2, "พ"), (3, "พฤ"), (4, "ศ")),
        widget=forms.CheckboxSelectMultiple,
    )
    series_end_mode = forms.ChoiceField(
        label="สิ้นสุดด้วย",
        required=False,
        choices=(("date", "วันที่"), ("count", "จำนวนครั้ง")),
        widget=forms.RadioSelect,
        initial="count",
    )
    series_end_date = BuddhistDateField(
        label="วันที่สิ้นสุดชุด",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "28/11/2569"}),
    )
    series_count = forms.IntegerField(label="จำนวนครั้ง", required=False, min_value=1)
    series_custom_dates = forms.CharField(
        label="วันที่กำหนดเอง",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "25/08/2569, 27/08/2569"}),
        help_text="คั่นแต่ละวันด้วยจุลภาคหรือขึ้นบรรทัดใหม่",
    )

    class Meta:
        model = Booking
        fields = [
            "title", "purpose", "online_meeting_url", "unit", "responsible_name", "responsible_phone",
            "attendees", "attendee_level", "layout", "equipment", "has_external_attendees",
            "external_attendees_note", "visibility", "note",
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
        is_new = self.instance._state.adding
        self.show_booking_summary = is_new and allowed_fields is None
        if not self.is_bound and is_new:
            if getattr(user, "display_name", "") and not self.initial.get("responsible_name"):
                self.initial["responsible_name"] = user.display_name
            if getattr(user, "phone", "") and not self.initial.get("responsible_phone"):
                self.initial["responsible_phone"] = user.phone
            if getattr(user, "unit_id", None) and not self.initial.get("unit"):
                self.initial["unit"] = user.unit_id
        # ช่องลิงก์ออนไลน์แสดงเฉพาะห้องหมวด online (งาน B) — ห้องอื่นตัดออกทั้งช่อง
        if room.room_category != Resource.Category.ONLINE:
            self.fields.pop("online_meeting_url", None)
        elif "online_meeting_url" in self.fields:
            self.fields["online_meeting_url"].widget.attrs.setdefault("placeholder", "https://meet.google.com/...")
            self.fields["online_meeting_url"].help_text = "เว้นว่างได้ เติมทีหลังได้จากหน้าแก้ไข · แสดงเฉพาะผู้จอง เจ้าหน้าที่ห้อง และผู้อนุมัติ"
        self.series_enabled = bool(getattr(room, "rule", None) and room.rule.allow_series)
        self.fields["series_count"].help_text = f"สูงสุด {room.rule.max_series_occurrences} ครั้ง" if self.series_enabled else ""
        self.fields["equipment"].queryset = Resource.objects.filter(
            resource_type=Resource.Type.EQUIPMENT,
            status=Resource.Status.ACTIVE,
        )
        if user.is_superuser:
            self.fields["unit"].queryset = Unit.objects.filter(is_active=True)
        else:
            self.fields["unit"].queryset = Unit.objects.filter(pk__in=_unit_ids_with_children(user.unit), is_active=True)
            if is_new and user.unit_id:
                self.initial.setdefault("unit", user.unit_id)

        fixed_items = [line.strip() for line in room.fixed_equipment.splitlines() if line.strip()]
        self.fields["fixed_equipment_choices"].choices = [(item, item) for item in fixed_items]
        if not is_new:
            local_start = timezone.localtime(self.instance.start_at)
            local_end = timezone.localtime(self.instance.end_at)
            self.initial.setdefault("date", local_start.date())
            self.initial.setdefault("start_time", local_start.strftime("%H:%M"))
            self.initial.setdefault("end_time", local_end.strftime("%H:%M"))
            selected = [line.strip() for line in self.instance.fixed_equipment_needed.splitlines() if line.strip()]
            self.initial.setdefault("fixed_equipment_choices", [item for item in selected if item in fixed_items])
            self.initial.setdefault("fixed_equipment_extra", "\n".join(item for item in selected if item not in fixed_items))
        elif self.series_enabled:
            initial_date = self.initial.get("date")
            if isinstance(initial_date, date):
                self.initial.setdefault("series_weekdays", [str(min(initial_date.weekday(), 4))])
            self.initial.setdefault("series_count", min(4, room.rule.max_series_occurrences))

        datalist_fields = ("title", "responsible_name", "responsible_phone", "attendee_level", "layout")
        unit = self.instance.unit if not is_new else getattr(user, "unit", None)
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
            self.series_enabled = False
        elif not self.series_enabled:
            for name in list(self.fields):
                if name.startswith("series_") or name == "is_series":
                    self.fields.pop(name)
        self.order_fields(
            [
                "date", "start_time", "end_time", "title", "purpose", "online_meeting_url", "unit", "responsible_name",
                "responsible_phone", "attendees", "attendee_level", "layout", "fixed_equipment_choices",
                "fixed_equipment_extra", "equipment", "has_external_attendees", "external_attendees_note",
                "visibility", "note",
                "is_series", "series_freq", "series_weekdays", "series_end_mode", "series_end_date",
                "series_count", "series_custom_dates",
            ]
        )

    @property
    def has_more_data(self):
        more_fields = {
            "attendee_level", "layout", "equipment", "fixed_equipment_choices", "fixed_equipment_extra",
            "has_external_attendees", "external_attendees_note", "visibility", "note", "is_series",
            "series_freq", "series_weekdays", "series_end_mode", "series_end_date", "series_count",
            "series_custom_dates",
        }
        names = more_fields.intersection(self.fields)
        if self.is_bound and any(name in self.errors for name in names):
            return True
        if self.is_bound:
            for name in names:
                value = self[name].value()
                if name == "visibility" and value in (None, "", Booking.Visibility.NORMAL):
                    continue
                if name in {"series_freq", "series_end_mode", "series_count"} and not self.data.get("is_series"):
                    continue
                if value not in (None, "", False, [], (), "False", "0"):
                    return True
            return False
        if self.instance.pk:
            return any((
                self.instance.attendee_level, self.instance.layout, self.instance.equipment.exists(),
                self.instance.fixed_equipment_needed, self.instance.has_external_attendees,
                self.instance.external_attendees_note, self.instance.visibility != Booking.Visibility.NORMAL, self.instance.note,
            ))
        return False

    def clean_series_custom_dates(self):
        value = self.cleaned_data.get("series_custom_dates", "")
        if not value.strip():
            self._parsed_series_custom_dates = []
            return ""
        values = value.replace(",", "\n").splitlines()
        field = BuddhistDateField()
        result = []
        for item in values:
            if item.strip():
                result.append(field.clean(item.strip()))
        self._parsed_series_custom_dates = sorted(set(result))
        return value

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
        if cleaned.get("is_series"):
            freq = cleaned.get("series_freq")
            if freq == BookingSeries.Frequency.WEEKLY and not cleaned.get("series_weekdays"):
                self.add_error("series_weekdays", "กรุณาเลือกอย่างน้อย 1 วัน")
            if freq == BookingSeries.Frequency.CUSTOM and not getattr(self, "_parsed_series_custom_dates", []):
                self.add_error("series_custom_dates", "กรุณาระบุวันที่อย่างน้อย 1 วัน")
            if freq != BookingSeries.Frequency.CUSTOM:
                if cleaned.get("series_end_mode") == "date" and not cleaned.get("series_end_date"):
                    self.add_error("series_end_date", "กรุณาระบุวันที่สิ้นสุดชุด")
                if cleaned.get("series_end_mode") == "count" and not cleaned.get("series_count"):
                    self.add_error("series_count", "กรุณาระบุจำนวนครั้ง")
                if cleaned.get("series_count") and cleaned["series_count"] > self.room.rule.max_series_occurrences:
                    self.add_error("series_count", f"ห้องนี้จองเป็นชุดได้ไม่เกิน {self.room.rule.max_series_occurrences} ครั้ง")
        return cleaned

    def series_params(self):
        cleaned = self.cleaned_data
        start_date = cleaned["start_at"].date()
        end_mode = cleaned.get("series_end_mode")
        return {
            "freq": cleaned.get("series_freq"),
            "weekdays": [int(item) for item in cleaned.get("series_weekdays", [])],
            "custom_dates": getattr(self, "_parsed_series_custom_dates", []),
            "start_date": start_date,
            "end_date": cleaned.get("series_end_date") if end_mode == "date" else None,
            "requested_count": cleaned.get("series_count") if end_mode == "count" else None,
            "time_start": cleaned["start_time"],
            "time_end": cleaned["end_time"],
        }

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


class AmendmentForm(forms.Form):
    date = BuddhistDateField(label="วันที่", widget=forms.TextInput(attrs={"placeholder": "27/08/2569"}))
    start_time = forms.TimeField(label="เริ่ม", widget=forms.Select(choices=time_choices()), input_formats=["%H:%M"])
    end_time = forms.TimeField(label="สิ้นสุด", widget=forms.Select(choices=time_choices()), input_formats=["%H:%M"])
    room = forms.ModelChoiceField(label="ห้อง", queryset=Resource.objects.none())
    equipment = forms.ModelMultipleChoiceField(
        label="อุปกรณ์ส่วนกลางชุดเต็มที่จะใช้จริง",
        queryset=Resource.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    attendees = forms.IntegerField(label="จำนวนผู้เข้าร่วม", min_value=1)
    has_external = forms.TypedChoiceField(
        label="ผู้เข้าร่วมภายนอก",
        choices=((False, "ไม่มี"), (True, "มี")),
        coerce=lambda value: str(value).lower() == "true",
        widget=forms.RadioSelect,
    )
    external_note = forms.CharField(label="รายละเอียดผู้เข้าร่วมภายนอก", required=False, max_length=200)
    reason = forms.CharField(
        label="เหตุผลที่ขอแก้ไข",
        required=False,
        max_length=300,
        widget=forms.TextInput(attrs={"placeholder": "เลือกเหตุผลที่เคยใช้หรือพิมพ์เอง", "list": "amendment-reasons"}),
    )

    def __init__(self, *args, booking: Booking, user, now=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .amendment_services import available_amendment_rooms

        self.booking = booking
        self.user = user
        self.now = now or timezone.now()
        local_start = timezone.localtime(booking.start_at)
        local_end = timezone.localtime(booking.end_at)
        self.initial.update(
            {
                "date": local_start.date(),
                "start_time": local_start.strftime("%H:%M"),
                "end_time": local_end.strftime("%H:%M"),
                "room": booking.room_id,
                "equipment": list(booking.equipment.values_list("pk", flat=True)),
                "attendees": booking.attendees,
                "has_external": booking.has_external_attendees,
                "external_note": booking.external_attendees_note,
            }
        )
        candidate_start, candidate_end = booking.start_at, booking.end_at
        if self.is_bound:
            try:
                day = BuddhistDateField().clean(self.data.get("date"))
                start_time = time.fromisoformat(self.data.get("start_time", ""))
                end_time = time.fromisoformat(self.data.get("end_time", ""))
                zone = timezone.get_current_timezone()
                candidate_start = timezone.make_aware(datetime.combine(day, start_time), zone)
                candidate_end = timezone.make_aware(datetime.combine(day, end_time), zone)
            except (TypeError, ValueError, forms.ValidationError):
                pass
        self.fields["room"].queryset = available_amendment_rooms(
            booking, candidate_start, candidate_end, user, self.now
        )
        self.fields["equipment"].queryset = Resource.objects.filter(
            resource_type=Resource.Type.EQUIPMENT,
            status=Resource.Status.ACTIVE,
        ).order_by("code")
        self.recent_reasons = list(
            booking.amendments.exclude(reason="").order_by("-submitted_at").values_list("reason", flat=True)[:10]
        )

    def clean(self):
        cleaned = super().clean()
        day = cleaned.get("date")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        if day and start_time and end_time:
            zone = timezone.get_current_timezone()
            cleaned["start_at"] = timezone.make_aware(datetime.combine(day, start_time), zone)
            cleaned["end_at"] = timezone.make_aware(datetime.combine(day, end_time), zone)
            if cleaned["end_at"] <= cleaned["start_at"]:
                raise forms.ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม")
        if cleaned.get("has_external") and not (cleaned.get("external_note") or "").strip():
            self.add_error("external_note", "กรุณาระบุจำนวนหรือหน่วยของผู้เข้าร่วมภายนอก")
        return cleaned

    def proposed(self):
        return {
            "room": self.cleaned_data["room"],
            "start_at": self.cleaned_data["start_at"],
            "end_at": self.cleaned_data["end_at"],
            "equipment": list(self.cleaned_data["equipment"]),
            "attendees": self.cleaned_data["attendees"],
            "has_external": self.cleaned_data["has_external"],
            "external_note": self.cleaned_data.get("external_note", ""),
            "reason": self.cleaned_data.get("reason", ""),
        }


class PreemptionForm(forms.Form):
    reason = forms.CharField(
        label="เหตุผล",
        max_length=300,
        widget=forms.TextInput(attrs={"list": "preemption-reasons", "placeholder": "เลือกเหตุผลที่เคยใช้หรือพิมพ์เอง"}),
    )
    reference_no = forms.CharField(label="เลขอ้างอิงคำสั่ง/หนังสือ", max_length=100)
    title = forms.CharField(label="ชื่อกิจกรรมที่จะเข้าแทน", max_length=200)
    unit = forms.ModelChoiceField(label="หน่วย", queryset=Unit.objects.filter(is_active=True).order_by("code"))
    responsible_name = forms.CharField(label="ผู้รับผิดชอบ", max_length=200)
    responsible_phone = forms.CharField(label="โทรศัพท์", max_length=30)
    date = BuddhistDateField(label="วันที่", widget=forms.TextInput(attrs={"placeholder": "27/08/2569"}))
    start_time = forms.TimeField(label="เริ่ม", widget=forms.Select(choices=time_choices()), input_formats=["%H:%M"])
    end_time = forms.TimeField(label="สิ้นสุด", widget=forms.Select(choices=time_choices()), input_formats=["%H:%M"])
    visibility = forms.ChoiceField(label="การมองเห็น", choices=Booking.Visibility.choices)
    replacement_room = forms.ChoiceField(label="ห้องทดแทน", required=False, widget=forms.RadioSelect)

    def __init__(self, *args, booking: Booking, actor, options, **kwargs):
        super().__init__(*args, **kwargs)
        self.booking = booking
        self.actor = actor
        self.options = options
        local_start = timezone.localtime(booking.start_at)
        local_end = timezone.localtime(booking.end_at)
        self.initial.update(
            {
                "date": local_start.date(),
                "start_time": local_start.strftime("%H:%M"),
                "end_time": local_end.strftime("%H:%M"),
                "unit": actor.unit_id,
                "responsible_name": actor.display_name,
                "responsible_phone": actor.phone,
                "visibility": Booking.Visibility.RESTRICTED,
            }
        )
        self.fields["replacement_room"].choices = [
            (str(item.room.pk), f"{item.room.code} {item.room.name} — {item.approval_label}") for item in options
        ] + [("", "ไม่มีห้องทดแทน")]
        self.recent_reasons = list(
            actor.ordered_preemptions.exclude(reason="").order_by("-created_at").values_list("reason", flat=True)[:10]
        )
        unit = getattr(actor, "unit", None)
        self.datalists = {
            name: frequent_values(unit, name)
            for name in ("title", "responsible_name", "responsible_phone")
        }
        for name in self.datalists:
            self.fields[name].widget.attrs["list"] = f"preemption-{name}"

    def clean(self):
        cleaned = super().clean()
        day = cleaned.get("date")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        if day and start_time and end_time:
            zone = timezone.get_current_timezone()
            start_at = timezone.make_aware(datetime.combine(day, start_time), zone)
            end_at = timezone.make_aware(datetime.combine(day, end_time), zone)
            cleaned["start_at"] = start_at
            cleaned["end_at"] = end_at
            if end_at <= start_at:
                raise forms.ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม")
            if end_at <= self.booking.start_at or start_at >= self.booking.end_at:
                raise forms.ValidationError("เวลาของงานที่เข้าแทนต้องซ้อนกับการจองเดิม")
        room_id = cleaned.get("replacement_room")
        allowed = {str(item.room.pk): item.room for item in self.options}
        if room_id and room_id not in allowed:
            self.add_error("replacement_room", "ห้องทดแทนที่เลือกไม่อยู่ในรายการที่ระบบเสนอ")
        cleaned["replacement_room_object"] = allowed.get(room_id)
        return cleaned

    def incoming_data(self):
        return {
            "title": self.cleaned_data["title"],
            "unit": self.cleaned_data["unit"],
            "responsible_name": self.cleaned_data["responsible_name"],
            "responsible_phone": self.cleaned_data["responsible_phone"],
            "start_at": self.cleaned_data["start_at"],
            "end_at": self.cleaned_data["end_at"],
            "visibility": self.cleaned_data["visibility"],
        }

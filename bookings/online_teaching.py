"""Focused teacher workflow for the three Signal School online teaching rooms.

Booking Core remains authoritative for time policy, blackout/outage, overlap holds,
submission state, cancellation and audit. This module owns authorization and the
short task-first presentation only; booking writes go through online_teaching_services.
"""
import calendar
from datetime import date, datetime, timedelta
from urllib.parse import parse_qsl, urlencode

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from accounts.models import Unit
from accounts.services import complete_contact_profile
from resources.models import Resource, ResourceRule

from .course_catalog import selectable_course_runs
from .forms import BuddhistDateField, time_choices
from .templatetags.thaidate import THAI_MONTHS_FULL
from .models import Booking, CourseRun
from .online_teaching_services import create_online_teaching_booking, suggest_online_rooms
from .services import (
    BookingConflict,
    find_available_rooms,
    next_quarter_start,
    THAI_WEEKDAYS_SHORT,
    search_date_choices,
    search_period_choices,
)


ONLINE_TEACHER_GROUP = "signalschool-teacher"
ONLINE_TEACHING_ROOM_CODES = (
    "STU-ONLINE-1",
    "STU-ONLINE-2",
    "STU-ONLINE-3",
)
# ชิปเวลาเริ่มทุกครึ่งชั่วโมง 07:00–17:30 (คาบสั้นสุด 30 นาทีจบไม่เกิน 18:00) แบ่งเช้า/บ่าย
ONLINE_START_GROUPS = (
    ("เช้า", tuple(f"{hour:02d}:{minute:02d}" for hour in range(7, 12) for minute in (0, 30))),
    ("บ่าย", tuple(f"{hour:02d}:{minute:02d}" for hour in range(12, 18) for minute in (0, 30))),
)
ONLINE_DURATION_MINUTES = (30, 60, 120)
ONLINE_QUERY_KEYS = {"day", "date", "start", "dur", "course_run", "purpose"}
ONLINE_CALENDAR_TARGET = "online-calendar"
ONLINE_CALENDAR_FALLBACK_DAYS = 90


def can_book_online_teaching(user) -> bool:
    """Stable authorization seam that future Signalschool SSO can map into."""
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(
        getattr(user, "is_superuser", False)
        or user.groups.filter(name=ONLINE_TEACHER_GROUP).exists()
    )


def online_booking_editable_fields(fields: set[str]) -> set[str]:
    """Online self-service keeps identity/course immutable after submission."""
    return set(fields).intersection({"online_meeting_url", "attendees", "note"})


def online_course_runs():
    """Shared course-run catalog adapter used by Teacher Self-Service."""
    return selectable_course_runs()


class CourseRunChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.display_name


def _room_queryset(*, active_only=True):
    queryset = (
        Resource.objects.filter(
            code__in=ONLINE_TEACHING_ROOM_CODES,
            resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.ONLINE,
        )
        .select_related("rule", "owner_unit")
        .prefetch_related("photos")
    )
    if active_only:
        queryset = queryset.filter(status=Resource.Status.ACTIVE)
    return queryset


def _ordered_rooms(*, active_only=True):
    by_code = {room.code: room for room in _room_queryset(active_only=active_only)}
    return [by_code[code] for code in ONLINE_TEACHING_ROOM_CODES if code in by_code]


def _require_teacher(user):
    if not can_book_online_teaching(user):
        raise PermissionDenied("เฉพาะครูที่ได้รับสิทธิ์จองห้องสอนออนไลน์")


def _room_availability(room, start_at, end_at, user) -> tuple[bool, str]:
    available, unavailable = find_available_rooms(
        start_at,
        end_at,
        user,
        room_categories=(Resource.Category.ONLINE,),
    )
    for item in available:
        if item.room.pk == room.pk:
            return True, "ว่างในช่วงเวลานี้"
    for item in unavailable:
        if item.room.pk == room.pk:
            return False, item.reason or "ห้องไม่ว่างในช่วงเวลานี้"
    return False, "ห้องนี้ไม่พร้อมให้จอง"


class OnlineTeachingBookingForm(forms.Form):
    """Legacy choose-room-first form kept for bookmarked online/<code>/ URLs."""

    date = BuddhistDateField(
        label="วันที่",
        widget=forms.TextInput(
            attrs={"placeholder": "24/08/2569", "inputmode": "numeric", "autocomplete": "off"}
        ),
    )
    start_time = forms.TimeField(
        label="เริ่ม",
        widget=forms.Select(choices=time_choices()),
        input_formats=["%H:%M"],
    )
    end_time = forms.TimeField(
        label="สิ้นสุด",
        widget=forms.Select(choices=time_choices()),
        input_formats=["%H:%M"],
    )
    course_run = CourseRunChoiceField(
        label="หลักสูตรและรุ่น",
        queryset=CourseRun.objects.none(),
        empty_label=None,
        error_messages={"invalid_choice": "หลักสูตร/รุ่นนี้ไม่ได้อยู่ในรายการที่เปิดใช้"},
    )
    purpose = forms.ChoiceField(
        label="วัตถุประสงค์",
        choices=Booking.Purpose.choices,
        initial=Booking.Purpose.TEACHING,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        runs = online_course_runs()
        self.fields["course_run"].queryset = runs
        self.course_catalog_ready = runs.exists()

    def clean(self):
        cleaned = super().clean()
        booking_date = cleaned.get("date")
        start_time = cleaned.get("start_time")
        end_time = cleaned.get("end_time")
        if booking_date and start_time and end_time:
            zone = timezone.get_current_timezone()
            start_at = timezone.make_aware(datetime.combine(booking_date, start_time), zone)
            end_at = timezone.make_aware(datetime.combine(booking_date, end_time), zone)
            if end_at <= start_at:
                self.add_error("end_time", "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม")
            else:
                cleaned["start_at"] = start_at
                cleaned["end_at"] = end_at
        return cleaned


def _parse_quick_day(params):
    today = timezone.localdate()
    day_value = (params.get("day") or "").strip()
    date_value = (params.get("date") or "").strip()
    if day_value and day_value != "other":
        try:
            booking_date = datetime.fromisoformat(day_value).date()
        except ValueError:
            return None, "กรุณาตรวจวันที่อีกครั้ง"
    elif date_value:
        try:
            booking_date = BuddhistDateField().clean(date_value)
        except ValidationError:
            return None, "กรุณาตรวจวันที่อีกครั้ง (วัน/เดือน/ปี พ.ศ.)"
    else:
        booking_date = today + timedelta(days=1)
    if booking_date < today:
        return None, "วันที่จองต้องไม่ย้อนหลัง"
    return booking_date, ""


def _selected_course(user, params, runs):
    requested = (params.get("course_run") or "").strip()
    by_id = {str(run.pk): run for run in runs}
    if requested:
        return by_id.get(requested), "" if requested in by_id else "หลักสูตร/รุ่นนี้ไม่ได้อยู่ในรายการที่เปิดใช้"
    run_ids = [run.pk for run in runs]
    last_id = (
        Booking.objects.filter(
            requester=user,
            room__room_category=Resource.Category.ONLINE,
            course_run_id__in=run_ids,
        )
        .exclude(course_run=None)
        .order_by("-created_at")
        .values_list("course_run_id", flat=True)
        .first()
    )
    if last_id:
        match = by_id.get(str(last_id))
        if match:
            return match, ""
    return (runs[0] if runs else None), ""


def _quick_selection(user, params):
    booking_date, error = _parse_quick_day(params)
    presets = search_period_choices()
    start_text = (params.get("start") or "09:00").strip()[:5]
    try:
        start_clock = datetime.strptime(start_text, "%H:%M").time()
    except ValueError:
        start_clock = None
        error = error or "กรุณาตรวจเวลาเริ่มอีกครั้ง"

    dur = (params.get("dur") or "60").strip().lower()
    duration_minutes = None
    start_at = end_at = None
    zone = timezone.get_current_timezone()
    if booking_date and dur in {"am", "pm"}:
        preset_index = 0 if dur == "am" else 1
        if len(presets) <= preset_index:
            error = error or "ยังไม่ได้ตั้งช่วงเวลานี้ในระบบ"
        else:
            preset = presets[preset_index]
            start_at = timezone.make_aware(
                datetime.combine(booking_date, datetime.strptime(preset["start"], "%H:%M").time()), zone
            )
            end_at = timezone.make_aware(
                datetime.combine(booking_date, datetime.strptime(preset["end"], "%H:%M").time()), zone
            )
            duration_minutes = int((end_at - start_at).total_seconds() // 60)
    elif booking_date and start_clock is not None:
        try:
            duration_minutes = int(dur)
        except ValueError:
            duration_minutes = None
        # UI เสนอ 30/60/120 นาที; ค่าอื่นที่เป็นช่วง 30 นาทีและไม่เกิน 4 ชม.
        # รับไว้สำหรับลิงก์ช่วงใกล้เคียงที่ระบบสร้างจาก preset เช้า/บ่ายเท่านั้น.
        if duration_minutes is None or duration_minutes < 30 or duration_minutes > 240 or duration_minutes % 30:
            error = error or "กรุณาเลือกระยะเวลาที่ระบบรองรับ"
        else:
            start_at = timezone.make_aware(datetime.combine(booking_date, start_clock), zone)
            end_at = start_at + timedelta(minutes=duration_minutes)

    if start_at and end_at and end_at <= start_at:
        error = error or "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม"
    if start_at and start_at < timezone.now():
        error = error or "เวลาเริ่มต้องไม่อยู่ในอดีต"

    runs = list(online_course_runs())
    selected_course, course_error = _selected_course(user, params, runs)
    error = error or course_error
    purpose = (params.get("purpose") or Booking.Purpose.TEACHING).strip()
    valid_purposes = {value for value, _ in Booking.Purpose.choices}
    if purpose not in valid_purposes:
        purpose = Booking.Purpose.TEACHING
        error = error or "วัตถุประสงค์ไม่ถูกต้อง"

    return {
        "date": booking_date,
        "day": booking_date.isoformat() if booking_date else "",
        "date_text": (
            f"{booking_date.day:02d}/{booking_date.month:02d}/{booking_date.year + 543}" if booking_date else ""
        ),
        "start": start_at,
        "end": end_at,
        "start_text": timezone.localtime(start_at).strftime("%H:%M") if start_at else start_text,
        "dur": dur,
        "duration_minutes": duration_minutes,
        "presets": presets,
        "runs": runs,
        "course": selected_course,
        "purpose": purpose,
        "error": error,
    }


def _selection_query(selection, *, start_at=None, end_at=None):
    explicit_slot = start_at is not None and end_at is not None
    start_at = start_at or selection.get("start")
    end_at = end_at or selection.get("end")
    params = {}
    if start_at and end_at:
        local_start = timezone.localtime(start_at)
        params["day"] = local_start.date().isoformat()
        params["start"] = local_start.strftime("%H:%M")
        if explicit_slot:
            params["dur"] = str(int((end_at - start_at).total_seconds() // 60))
        else:
            params["dur"] = selection.get("dur") or str(int((end_at - start_at).total_seconds() // 60))
    elif selection.get("date"):
        params["day"] = selection["date"].isoformat()
        params["start"] = selection.get("start_text") or "09:00"
        params["dur"] = selection.get("dur") or "60"
    if selection.get("course"):
        params["course_run"] = str(selection["course"].pk)
    params["purpose"] = selection.get("purpose") or Booking.Purpose.TEACHING
    return urlencode(params)


def _online_calendar(selection, month_param, rooms):
    """ตารางเดือนสำหรับ "เลือกวันอื่น" — กดวันได้เลย ไม่ต้องพิมพ์วันที่."""
    today = timezone.localdate()
    advance_days = [
        room.rule.max_advance_days
        for room in rooms
        if getattr(room, "rule", None) is not None and room.rule.max_advance_days
    ]
    last_day = today + timedelta(days=max(advance_days) if advance_days else ONLINE_CALENDAR_FALLBACK_DAYS)

    shown = selection["date"] if selection["date"] and today <= selection["date"] <= last_day else today
    try:
        year, month = (int(part) for part in (month_param or "").split("-"))
        first = date(year, month, 1)
    except (TypeError, ValueError):
        first = shown.replace(day=1)
    first = min(max(first, today.replace(day=1)), last_day.replace(day=1))

    weeks = []
    for week in calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month):
        weeks.append(
            [
                {
                    "date": day,
                    "value": day.isoformat(),
                    "in_month": day.month == first.month,
                    "enabled": day.month == first.month and today <= day <= last_day,
                    "selected": day == selection["date"],
                    "today": day == today,
                }
                for day in week
            ]
        )

    def month_link(target):
        if target < today.replace(day=1) or target > last_day.replace(day=1):
            return ""
        params = dict(parse_qsl(_selection_query(selection)))
        params["cal"] = f"{target.year:04d}-{target.month:02d}"
        return reverse("bookings:online_teaching_home") + "?" + urlencode(params)

    return {
        "title": f"{THAI_MONTHS_FULL[first.month]} {first.year + 543}",
        "weekdays": THAI_WEEKDAYS_SHORT,
        "weeks": weeks,
        "prev_url": month_link((first - timedelta(days=1)).replace(day=1)),
        "next_url": month_link((first + timedelta(days=31)).replace(day=1)),
    }


def _online_home_context(request):
    if not can_book_online_teaching(request.user):
        return {
            "access_denied": True,
            "profile_complete": False,
            "rooms": [],
            "alternatives": [],
        }

    selection = _quick_selection(request.user, request.GET)
    profile_complete = bool(request.user.unit_id and (request.user.phone or "").strip())
    rooms = []
    alternatives = []
    if not selection["error"] and selection["start"] and selection["end"]:
        rooms, alternatives = suggest_online_rooms(
            user=request.user,
            start_at=selection["start"],
            end_at=selection["end"],
        )

    for alternative in alternatives:
        alternative["url"] = (
            reverse("bookings:online_teaching_home")
            + "?"
            + _selection_query(
                selection,
                start_at=alternative["start_at"],
                end_at=alternative["end_at"],
            )
        )

    day_choices = search_date_choices()
    chip_days = {choice["value"] for choice in day_choices}

    duration_choices = [
        {"value": "30", "label": "30 นาที"},
        {"value": "60", "label": "1 ชม."},
        {"value": "120", "label": "2 ชม."},
    ]
    if len(selection["presets"]) >= 1:
        duration_choices.append({"value": "am", "label": selection["presets"][0]["label"]})
    if len(selection["presets"]) >= 2:
        duration_choices.append({"value": "pm", "label": selection["presets"][1]["label"]})

    ordered_rooms = _ordered_rooms(active_only=True)
    legacy_room = ordered_rooms[0] if ordered_rooms else None
    return {
        "access_denied": False,
        "selection": selection,
        "day_choices": day_choices,
        "day_in_chips": selection["day"] in chip_days,
        "calendar": _online_calendar(selection, request.GET.get("cal"), ordered_rooms),
        "calendar_open": bool(request.GET.get("cal")) or (bool(selection["day"]) and selection["day"] not in chip_days),
        "start_groups": ONLINE_START_GROUPS,
        "duration_choices": duration_choices,
        "purpose_choices": Booking.Purpose.choices,
        "profile_complete": profile_complete,
        "profile_units": Unit.objects.filter(is_active=True).order_by("code"),
        "rooms": rooms,
        "alternatives": alternatives,
        "legacy_room": legacy_room,
        "query_string": _selection_query(selection),
    }


@login_required
def online_teaching_home(request):
    context = _online_home_context(request)
    htmx = getattr(request, "htmx", False)
    if not htmx or context.get("access_denied"):
        template = "bookings/online_teaching_home.html"
    elif htmx.target == ONLINE_CALENDAR_TARGET:
        template = "bookings/partials/online_calendar.html"
    else:
        template = "bookings/partials/online_results.html"
    response = render(request, template, context)
    if request.user.is_authenticated:
        response["Cache-Control"] = "private, no-store"
    return response


def _parse_quick_datetime(value, label):
    parsed = parse_datetime((value or "").strip())
    if parsed is None:
        raise ValidationError(f"{label}ไม่ถูกต้อง")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _safe_return_query(raw):
    pairs = []
    for key, value in parse_qsl(raw or "", keep_blank_values=False):
        if key in ONLINE_QUERY_KEYS:
            pairs.append((key, value))
    return urlencode(pairs)


@login_required
@require_POST
def online_teaching_quick_book(request):
    _require_teacher(request.user)
    try:
        start_at = _parse_quick_datetime(request.POST.get("start_at"), "เวลาเริ่ม")
        end_at = _parse_quick_datetime(request.POST.get("end_at"), "เวลาสิ้นสุด")
        if timezone.localdate(start_at) != timezone.localdate(end_at):
            raise ValidationError("การจองห้องสอนออนไลน์ต้องอยู่ในวันเดียวกัน")
        room = Resource.objects.filter(pk=request.POST.get("room")).select_related("rule").first()
        if room is None:
            raise ValidationError("ไม่พบห้องที่เลือก")
        course_run = selectable_course_runs().filter(pk=request.POST.get("course_run")).first()
        if course_run is None:
            raise ValidationError("หลักสูตร/รุ่นนี้ไม่ได้อยู่ในรายการที่เปิดใช้")
        purpose = request.POST.get("purpose") or Booking.Purpose.TEACHING
        if purpose not in {value for value, _ in Booking.Purpose.choices}:
            raise ValidationError("วัตถุประสงค์ไม่ถูกต้อง")
        booking = create_online_teaching_booking(
            user=request.user,
            room=room,
            start_at=start_at,
            end_at=end_at,
            course_run=course_run,
            purpose=purpose,
        )
    except BookingConflict:
        messages.error(request, "ห้องนี้เพิ่งถูกจอง กรุณาเลือกห้องอื่น")
    except ValidationError as exc:
        messages.error(request, " · ".join(exc.messages))
    else:
        messages.success(request, f"จอง {booking.room.name} สำเร็จและยืนยันอัตโนมัติแล้ว")
        return redirect("bookings:booking_pass", id=booking.id)

    query = _safe_return_query(request.POST.get("return_query"))
    target = reverse("bookings:online_teaching_home")
    return redirect(f"{target}?{query}" if query else target)


@login_required
@require_POST
def online_teaching_profile(request):
    _require_teacher(request.user)
    unit = None
    if not request.user.unit_id:
        unit = Unit.objects.filter(pk=request.POST.get("unit"), is_active=True).first()
    try:
        complete_contact_profile(request.user, unit, request.POST.get("phone", ""))
    except ValidationError as exc:
        messages.error(request, " · ".join(exc.messages))
    else:
        messages.success(request, "บันทึกข้อมูลสำหรับการจองเรียบร้อยแล้ว")
    query = _safe_return_query(request.POST.get("return_query"))
    target = reverse("bookings:online_teaching_home")
    return redirect(f"{target}?{query}" if query else target)


@login_required
def online_teaching_book(request, code):
    """Legacy choose-room-first URL, kept for bookmarks and old links."""
    _require_teacher(request.user)
    room = get_object_or_404(_room_queryset(active_only=True), code=code)
    rule = getattr(room, "rule", None)
    if rule is None or rule.approval_policy != ResourceRule.ApprovalPolicy.AUTO:
        raise PermissionDenied("ห้องนี้ยังไม่ได้ตั้งนโยบายจองอัตโนมัติสำหรับครู")
    if not request.user.unit_id:
        raise PermissionDenied("บัญชีครูต้องมีสังกัดก่อนจองห้อง")
    if not (request.user.phone or "").strip():
        raise PermissionDenied("บัญชีครูต้องมีเบอร์โทรศัพท์ก่อนจองห้อง")

    if request.method == "GET":
        start_at = next_quarter_start() + timedelta(days=1)
        end_at = start_at + timedelta(hours=1)
        form = OnlineTeachingBookingForm(
            initial={
                "date": timezone.localdate(start_at),
                "start_time": timezone.localtime(start_at).strftime("%H:%M"),
                "end_time": timezone.localtime(end_at).strftime("%H:%M"),
                "purpose": Booking.Purpose.TEACHING,
            }
        )
        availability = None
    else:
        form = OnlineTeachingBookingForm(request.POST)
        availability = None
        if form.is_valid():
            start_at = form.cleaned_data["start_at"]
            end_at = form.cleaned_data["end_at"]
            is_available, reason = _room_availability(room, start_at, end_at, request.user)
            availability = {"ok": is_available, "message": reason}
            if request.POST.get("action") == "book":
                if not is_available:
                    form.add_error(None, reason)
                else:
                    try:
                        booking = create_online_teaching_booking(
                            user=request.user,
                            room=room,
                            start_at=start_at,
                            end_at=end_at,
                            course_run=form.cleaned_data["course_run"],
                            purpose=form.cleaned_data["purpose"],
                        )
                    except BookingConflict as exc:
                        form.add_error(None, str(exc))
                    except ValidationError as exc:
                        for message in exc.messages:
                            form.add_error(None, message)
                    else:
                        messages.success(request, f"จอง {booking.room.name} สำเร็จและยืนยันอัตโนมัติแล้ว")
                        return redirect("bookings:booking_pass", id=booking.id)

    return render(
        request,
        "bookings/online_teaching_book.html",
        {
            "room": room,
            "form": form,
            "availability": availability,
            "course_count": online_course_runs().count(),
        },
    )

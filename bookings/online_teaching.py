"""Focused teacher workflow for the three Signal School online teaching rooms.

Booking Core remains authoritative for time policy, blackout/outage, overlap holds,
submission state, cancellation and audit.  This module only owns the feature-policy
layer: teacher authorization, room allowlist, course catalog choices and compact UI.
"""
from datetime import datetime, timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from audit.services import audit, model_snapshot
from notifications.services import notify_submitted
from resources.models import Resource, ResourceRule

from .forms import BuddhistDateField, time_choices
from .models import Booking, ReferenceValue
from .services import BookingConflict, find_available_rooms, next_quarter_start, submit_booking


ONLINE_TEACHER_GROUP = "signalschool-teacher"
ONLINE_TEACHING_ROOM_CODES = (
    "STU-ONLINE-1",
    "STU-ONLINE-2",
    "STU-ONLINE-3",
)


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


def online_course_titles() -> list[str]:
    """Current course catalog adapter.

    seed_courses.py already publishes the canonical configured course titles into
    ReferenceValue(attendee_level).  The focused workflow consumes only active rows
    and never accepts arbitrary free text.  A future external course service can
    replace this adapter without changing Booking Core.
    """
    return list(
        ReferenceValue.objects.filter(field="attendee_level", is_active=True)
        .order_by("order", "value")
        .values_list("value", flat=True)
    )


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
    course = forms.ChoiceField(label="หลักสูตร", choices=())
    purpose = forms.ChoiceField(
        label="วัตถุประสงค์",
        choices=Booking.Purpose.choices,
        initial=Booking.Purpose.TEACHING,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        titles = online_course_titles()
        self.fields["course"].choices = [(title, title) for title in titles]
        self.course_catalog_ready = bool(titles)

    def clean_course(self):
        value = self.cleaned_data["course"]
        if not ReferenceValue.objects.filter(
            field="attendee_level", value=value, is_active=True
        ).exists():
            raise forms.ValidationError("หลักสูตรนี้ไม่ได้อยู่ในรายการที่เปิดใช้")
        return value

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


@login_required
def online_teaching_home(request):
    _require_teacher(request.user)
    rooms = _ordered_rooms(active_only=True)
    next_start = next_quarter_start()
    next_end = next_start + timedelta(hours=1)
    available, _ = find_available_rooms(
        next_start,
        next_end,
        request.user,
        room_categories=(Resource.Category.ONLINE,),
    )
    available_ids = {item.room.pk for item in available}
    cards = [
        {
            "room": room,
            "available_now": room.pk in available_ids,
        }
        for room in rooms
    ]
    return render(
        request,
        "bookings/online_teaching_home.html",
        {
            "cards": cards,
            "expected_room_count": len(ONLINE_TEACHING_ROOM_CODES),
            "configured_room_count": len(rooms),
            "next_start": next_start,
            "next_end": next_end,
            "course_count": len(online_course_titles()),
        },
    )


@login_required
def online_teaching_book(request, code):
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
                    course = form.cleaned_data["course"]
                    booking = Booking(
                        room=room,
                        requester=request.user,
                        unit=request.user.unit,
                        responsible_name=request.user.display_name,
                        responsible_phone=(request.user.phone or "").strip(),
                        title=course,
                        attendee_level=course,
                        purpose=form.cleaned_data["purpose"],
                        start_at=start_at,
                        end_at=end_at,
                        attendees=1,
                        visibility=Booking.Visibility.NORMAL,
                        has_external_attendees=False,
                    )
                    try:
                        booking.full_clean()
                        booking.save()
                        submit_booking(booking)
                    except BookingConflict as exc:
                        if booking.pk:
                            booking.delete()
                        form.add_error(None, str(exc))
                    except ValidationError as exc:
                        if booking.pk:
                            booking.delete()
                        for message in exc.messages:
                            form.add_error(None, message)
                    else:
                        if booking.request_status != Booking.RequestStatus.APPROVED:
                            booking.delete()
                            form.add_error(None, "นโยบายห้องไม่อนุญาตการยืนยันอัตโนมัติ")
                        else:
                            audit(
                                request.user,
                                "bookings.booking",
                                booking.pk,
                                "online_teaching_booked",
                                after=model_snapshot(booking),
                            )
                            notify_submitted(booking)
                            messages.success(
                                request,
                                f"จอง {room.name} สำเร็จและยืนยันอัตโนมัติแล้ว",
                            )
                            return redirect("bookings:my_bookings")

    return render(
        request,
        "bookings/online_teaching_book.html",
        {
            "room": room,
            "form": form,
            "availability": availability,
            "course_count": len(online_course_titles()),
        },
    )

from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from resources.models import Resource, ResourceRule

from .forms import BookingForm, BuddhistDateField, time_choices
from .models import Booking
from .services import (
    BookingConflict,
    calendar_label,
    can_view_details,
    cancel_booking,
    editable_fields,
    find_available_rooms,
    self_service_message,
    submit_booking,
)


def _parse_calendar_datetime(value: str | None, fallback: datetime) -> datetime:
    parsed = parse_datetime(value or "") or fallback
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _search_values(request):
    tomorrow = timezone.localdate() + timedelta(days=1)
    date_text = request.GET.get("date") or tomorrow.isoformat()
    try:
        booking_date = BuddhistDateField().clean(date_text)
        start_time = datetime.strptime(request.GET.get("start", "09:00")[:5], "%H:%M").time()
        end_time = datetime.strptime(request.GET.get("end", "10:00")[:5], "%H:%M").time()
        zone = timezone.get_current_timezone()
        start = timezone.make_aware(datetime.combine(booking_date, start_time), zone)
        end = timezone.make_aware(datetime.combine(booking_date, end_time), zone)
    except (TypeError, ValueError, ValidationError):
        return None, None, date_text
    display_date = f"{booking_date.day:02d}/{booking_date.month:02d}/{booking_date.year + 543}"
    return start, end, display_date


def _booking_queryset():
    return Booking.objects.select_related("room", "room__rule", "unit", "requester").prefetch_related("equipment")


@login_required
def calendar_view(request):
    rooms = Resource.objects.filter(resource_type=Resource.Type.ROOM, status=Resource.Status.ACTIVE)
    buildings = rooms.exclude(building="").values_list("building", flat=True).distinct().order_by("building")
    return render(request, "bookings/calendar.html", {"rooms": rooms, "buildings": buildings})


@login_required
def calendar_events(request):
    now = timezone.now()
    start = _parse_calendar_datetime(request.GET.get("start"), now - timedelta(days=30))
    end = _parse_calendar_datetime(request.GET.get("end"), now + timedelta(days=90))
    bookings = _booking_queryset().filter(
        request_status__in=Booking.HOLDING_STATUSES,
        start_at__lt=end,
        end_at__gt=start,
    )
    if request.GET.get("room"):
        bookings = bookings.filter(room__code=request.GET["room"])
    if request.GET.get("building"):
        bookings = bookings.filter(room__building=request.GET["building"])

    events = []
    for booking in bookings:
        can_open = can_view_details(request.user, booking)
        classes = [f"status-{booking.request_status}"]
        if not can_open:
            classes.append("masked")
        events.append(
            {
                "id": str(booking.id),
                "title": calendar_label(request.user, booking),
                "start": booking.start_at.isoformat(),
                "end": booking.end_at.isoformat(),
                "url": reverse("bookings:booking_detail", args=[booking.id]),
                "classNames": classes,
                "extendedProps": {"status": booking.request_status, "room": booking.room.code},
            }
        )
        rule = getattr(booking.room, "rule", None)
        if rule and rule.buffer_before_min:
            events.append(
                {
                    "start": (booking.start_at - timedelta(minutes=rule.buffer_before_min)).isoformat(),
                    "end": booking.start_at.isoformat(),
                    "display": "background",
                    "classNames": ["buffer"],
                    "title": "",
                }
            )
        if rule and rule.buffer_after_min:
            events.append(
                {
                    "start": booking.end_at.isoformat(),
                    "end": (booking.end_at + timedelta(minutes=rule.buffer_after_min)).isoformat(),
                    "display": "background",
                    "classNames": ["buffer"],
                    "title": "",
                }
            )
    return JsonResponse(events, safe=False)


@login_required
def book_search(request):
    equipment = Resource.objects.filter(resource_type=Resource.Type.EQUIPMENT, status=Resource.Status.ACTIVE)
    start, end, date_text = _search_values(request)
    available = unavailable = []
    searched = bool(request.GET.get("search") or request.GET.get("date"))
    error = ""
    equipment_codes = request.GET.getlist("equipment")
    try:
        attendees = int(request.GET.get("attendees", "") or 0) or None
    except ValueError:
        attendees = None
        error = "จำนวนผู้เข้าร่วมต้องเป็นตัวเลข"
    if searched and start and end and not error:
        if end <= start:
            error = "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม"
        else:
            available, unavailable = find_available_rooms(
                start,
                end,
                request.user,
                attendees=attendees,
                equipment_codes=equipment_codes,
            )
    elif searched and not start:
        error = "กรุณาตรวจวันที่และเวลาอีกครั้ง"

    context = {
        "available": available,
        "unavailable": unavailable,
        "equipment": equipment,
        "equipment_codes": equipment_codes,
        "attendees": attendees or "",
        "date_value": date_text,
        "start_value": request.GET.get("start", "09:00")[:5],
        "end_value": request.GET.get("end", "10:00")[:5],
        "time_options": time_choices(),
        "searched": searched,
        "error": error,
        "query_string": request.GET.urlencode(),
    }
    template = "bookings/partials/room_list.html" if getattr(request, "htmx", False) else "bookings/book_search.html"
    return render(request, template, context)


def _initial_from_query(request):
    start, end, date_text = _search_values(request)
    initial = {"date": date_text}
    if start and end:
        initial.update(
            {
                "date": timezone.localdate(start),
                "start_time": timezone.localtime(start).strftime("%H:%M"),
                "end_time": timezone.localtime(end).strftime("%H:%M"),
            }
        )
    if request.user.unit_id:
        initial["unit"] = request.user.unit_id
    if request.user.phone:
        initial["responsible_phone"] = request.user.phone
    initial["responsible_name"] = request.user.display_name
    if request.GET.get("attendees", "").isdigit():
        initial["attendees"] = int(request.GET["attendees"])
    initial["equipment"] = Resource.objects.filter(code__in=request.GET.getlist("equipment"))
    return initial


@login_required
def book_form(request, code):
    room = get_object_or_404(
        Resource.objects.select_related("rule"),
        code=code,
        resource_type=Resource.Type.ROOM,
    )
    booking = Booking(room=room, requester=request.user, unit=request.user.unit)
    if request.method == "POST":
        form = BookingForm(request.POST, user=request.user, room=room, instance=booking)
        if form.is_valid():
            booking = form.save()
            booking.requester = request.user
            booking.save(update_fields=["requester"])
            if request.POST.get("action") == "draft":
                messages.success(request, "บันทึกร่างแล้ว")
                return redirect("bookings:booking_detail", id=booking.id)
            try:
                submit_booking(booking)
            except BookingConflict as exc:
                booking.delete()
                form.add_error(None, f"{exc} กรุณาเลือกเวลาหรือห้องอื่น ข้อมูลที่กรอกยังอยู่ครบ")
            except ValidationError as exc:
                booking.delete()
                for message in exc.messages:
                    form.add_error(None, message)
            else:
                messages.success(request, "ส่งคำขอจองห้องแล้ว")
                return redirect("bookings:booking_detail", id=booking.id)
    else:
        form = BookingForm(user=request.user, room=room, instance=booking, initial=_initial_from_query(request))
    return render(request, "bookings/book_form.html", {"form": form, "room": room})


@login_required
def booking_detail(request, id):
    booking = get_object_or_404(_booking_queryset(), id=id)
    full_details = can_view_details(request.user, booking)
    if not full_details:
        return render(request, "bookings/booking_masked.html", {"booking": booking})
    owner = booking.requester_id == request.user.pk or request.user.is_superuser
    fields = editable_fields(booking) if owner else set()
    return render(
        request,
        "bookings/booking_detail.html",
        {
            "booking": booking,
            "can_edit": bool(fields),
            "can_cancel": owner and not self_service_message(booking) and booking.request_status not in {
                Booking.RequestStatus.CANCELLED,
                Booking.RequestStatus.REJECTED,
                Booking.RequestStatus.EXPIRED,
            },
            "deadline_message": self_service_message(booking) if owner else "",
        },
    )


@login_required
def booking_edit(request, id):
    booking = get_object_or_404(_booking_queryset(), id=id)
    if booking.requester_id != request.user.pk and not request.user.is_superuser:
        raise PermissionDenied
    fields = editable_fields(booking)
    if not fields:
        messages.error(request, self_service_message(booking) or "การจองสถานะนี้แก้ไขไม่ได้")
        return redirect("bookings:booking_detail", id=booking.id)
    if request.method == "POST":
        form = BookingForm(request.POST, user=request.user, room=booking.room, instance=booking, allowed_fields=fields)
        if form.is_valid():
            booking = form.save()
            booking.revision += 1
            booking.save(update_fields=["revision", "updated_at"])
            messages.success(request, "แก้ไขรายละเอียดแล้ว")
            return redirect("bookings:booking_detail", id=booking.id)
    else:
        form = BookingForm(user=request.user, room=booking.room, instance=booking, allowed_fields=fields)
    return render(request, "bookings/booking_edit.html", {"form": form, "booking": booking})


@login_required
@require_POST
def booking_cancel(request, id):
    booking = get_object_or_404(_booking_queryset(), id=id)
    try:
        cancel_booking(booking, request.user)
    except (PermissionError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "ยกเลิกการจองและคืนช่วงเวลาแล้ว")
    return redirect("bookings:booking_detail", id=booking.id)


@login_required
@require_POST
def booking_submit(request, id):
    booking = get_object_or_404(_booking_queryset(), id=id, requester=request.user)
    try:
        submit_booking(booking)
    except (BookingConflict, ValidationError, ValueError) as exc:
        text = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        messages.error(request, text)
    else:
        messages.success(request, "ส่งคำขอจองห้องแล้ว")
    return redirect("bookings:booking_detail", id=booking.id)


@login_required
@require_POST
def booking_delete_draft(request, id):
    booking = get_object_or_404(Booking, id=id, requester=request.user)
    if booking.request_status != Booking.RequestStatus.DRAFT:
        raise Http404
    booking.delete()
    messages.success(request, "ลบร่างแล้ว")
    return redirect("bookings:my_bookings")


@login_required
def my_bookings(request):
    now = timezone.now()
    bookings = _booking_queryset().filter(requester=request.user)
    groups = {
        "upcoming": bookings.filter(start_at__gte=now).exclude(request_status__in=[Booking.RequestStatus.DRAFT, Booking.RequestStatus.CANCELLED, Booking.RequestStatus.REJECTED]),
        "drafts": bookings.filter(request_status=Booking.RequestStatus.DRAFT),
        "past": bookings.filter(end_at__lt=now).exclude(request_status__in=[Booking.RequestStatus.CANCELLED, Booking.RequestStatus.REJECTED]),
        "closed": bookings.filter(request_status__in=[Booking.RequestStatus.CANCELLED, Booking.RequestStatus.REJECTED, Booking.RequestStatus.EXPIRED]),
    }
    tab = request.GET.get("tab", "upcoming")
    if tab not in groups:
        tab = "upcoming"
    return render(request, "bookings/my_bookings.html", {"groups": groups, "tab": tab, "bookings": groups[tab]})

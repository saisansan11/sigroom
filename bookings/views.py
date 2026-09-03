from datetime import datetime, time, timedelta

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

from resources.models import Blackout, Resource, ResourceRule
from resources.services import active_outages
from approvals.services import can_decide, recent_rejection_reasons
from notifications.services import notify_submitted
from audit.services import audit, model_snapshot
from usage.services import can_manage_usage, recent_bookings_for

from .amendment_services import amendment_ref, evaluate_amendment_policy, submit_amendment, withdraw_amendment
from .forms import AmendmentForm, BookingForm, BuddhistDateField, PreemptionForm, time_choices
from .models import Booking, BookingAmendment, BookingSeries, Preemption
from .preemption_services import acknowledge, can_preempt, execute_preemption, replacement_options
from .series_services import cancel_remaining, create_series, preview_series, series_ref
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


def _today_board(request, rooms, now):
    """แถวเวลารายห้องของวันนี้ (07:00–21:00) พร้อมตัวเลขสรุปสถานการณ์"""
    zone = timezone.get_current_timezone()
    day = timezone.localdate(now)
    board_start = timezone.make_aware(datetime.combine(day, time(7)), zone)
    board_end = timezone.make_aware(datetime.combine(day, time(21)), zone)
    span = (board_end - board_start).total_seconds()

    def pct(dt):
        return max(0.0, min(100.0, (dt - board_start).total_seconds() / span * 100))

    bookings_by_room = {}
    todays = (
        _booking_queryset()
        .filter(
            room__in=rooms,
            request_status__in=Booking.HOLDING_STATUSES,
            start_at__lt=board_end,
            end_at__gt=board_start,
        )
        .order_by("start_at")
    )
    for booking in todays:
        bookings_by_room.setdefault(booking.room_id, []).append(booking)

    rows, in_use, busy_now = [], set(), set()
    for room in rooms:
        blocks = []
        for outage in active_outages(room, board_start, board_end):
            blocks.append({
                "cls": "outage",
                "left": pct(outage.start_at),
                "width": max(1.5, pct(outage.end_at) - pct(outage.start_at)),
                "label": f"งดใช้ — {outage.reason}",
            })
            if outage.start_at <= now < outage.end_at:
                busy_now.add(room.id)
        for booking in bookings_by_room.get(room.id, []):
            if can_view_details(request.user, booking):
                label = booking.title
            elif booking.visibility == Booking.Visibility.NORMAL:
                label = f"ไม่ว่าง — {booking.unit.name}"
            else:
                label = "ไม่ว่าง"
            active_now = booking.start_at <= now < booking.end_at
            if booking.request_status == Booking.RequestStatus.PENDING:
                cls = "pending"
            elif active_now:
                cls = "in-use"
            else:
                cls = "approved"
            if active_now:
                # ทั้งอนุมัติแล้วและรออนุมัติถือครองเวลา (FR-10) จึงไม่ว่างทั้งคู่
                busy_now.add(room.id)
                if booking.request_status == Booking.RequestStatus.APPROVED:
                    in_use.add(room.id)
            blocks.append({
                "cls": cls,
                "left": pct(booking.start_at),
                "width": max(1.5, pct(booking.end_at) - pct(booking.start_at)),
                "label": label,
            })
        rows.append({"room": room, "blocks": blocks})

    now_pct = pct(now) if board_start <= now <= board_end else None
    total = len(rows)
    return {
        "board_today": day,
        "board_rows": rows,
        "board_hours": list(range(7, 21)),
        "board_now_pct": now_pct,
        "board_now_label": timezone.localtime(now).strftime("%H:%M"),
        "stat_total": total,
        "stat_in_use": len(in_use),
        "stat_free_now": total - len(busy_now),
    }


def calendar_view(request):
    rooms = Resource.objects.filter(resource_type=Resource.Type.ROOM, status=Resource.Status.ACTIVE).order_by("code")
    selected_category = request.GET.get("category", "").strip()
    if selected_category:
        rooms = rooms.filter(room_category=selected_category)
    buildings = rooms.exclude(building="").values_list("building", flat=True).distinct().order_by("building")
    now = timezone.now()
    if request.user.is_authenticated:
        next_booking = (
            _booking_queryset()
            .filter(
                requester=request.user,
                request_status__in=Booking.HOLDING_STATUSES,
                end_at__gt=now,
            )
            .order_by("start_at")
            .first()
        )
        usage_today_count = None
        if can_manage_usage(request.user):
            today = timezone.localdate(now)
            usage_today_count = sum(
                1 for booking in recent_bookings_for(request.user, now) if timezone.localdate(booking.end_at) == today
            )
        my_pending_count = _booking_queryset().filter(
            requester=request.user, request_status=Booking.RequestStatus.PENDING, end_at__gt=now
        ).count()
    else:
        next_booking = None
        usage_today_count = None
        my_pending_count = 0

    category_choices = [
        ("", "ทุกหมวดห้อง"),
        (Resource.Category.CLASSROOM, "ห้องเรียน"),
        (Resource.Category.LODGING, "ห้องพัก"),
        (Resource.Category.MEETING, "ห้องประชุม"),
        (Resource.Category.LAB, "ห้องสอนปฏิบัติ"),
    ]

    context = {
        "rooms": rooms,
        "buildings": buildings,
        "selected_category": selected_category,
        "category_choices": category_choices,
        "next_booking": next_booking,
        "usage_today_count": usage_today_count,
        "my_pending_count": my_pending_count,
    }
    context.update(_today_board(request, rooms, now))
    return render(request, "bookings/calendar.html", context)


def calendar_events(request):
    now = timezone.now()
    start = _parse_calendar_datetime(request.GET.get("start"), now - timedelta(days=30))
    end = _parse_calendar_datetime(request.GET.get("end"), now + timedelta(days=90))
    bookings = _booking_queryset().filter(
        request_status__in=Booking.HOLDING_STATUSES,
        start_at__lt=end,
        end_at__gt=start,
    )
    if request.GET.get("category"):
        bookings = bookings.filter(room__room_category=request.GET["category"])
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
                "url": reverse("bookings:booking_detail", args=[booking.id]) if can_open else "#",
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

    amendments = (
        BookingAmendment.objects.filter(
            status=BookingAmendment.Status.PENDING,
        )
        .select_related("booking", "booking__room", "booking__unit", "proposed_room")
    )
    for amendment in amendments:
        proposed_start = amendment.proposed_start_at or amendment.booking.start_at
        proposed_end = amendment.proposed_end_at or amendment.booking.end_at
        proposed_room = amendment.proposed_room or amendment.booking.room
        if proposed_start >= end or proposed_end <= start:
            continue
        if request.GET.get("room") and proposed_room.code != request.GET["room"]:
            continue
        if request.GET.get("building") and proposed_room.building != request.GET["building"]:
            continue
        can_open = can_view_details(request.user, amendment.booking)
        if can_open:
            title = f"รออนุมัติแก้ไข: {amendment.booking.title} — {proposed_room.code}"
        elif amendment.booking.visibility == Booking.Visibility.NORMAL:
            title = f"รออนุมัติแก้ไข: ไม่ว่าง — {amendment.booking.unit.name}"
        else:
            title = "รออนุมัติแก้ไข: ไม่ว่าง"
        events.append(
            {
                "id": f"amendment-{amendment.pk}",
                "title": title,
                "start": proposed_start.isoformat(),
                "end": proposed_end.isoformat(),
                "url": reverse("bookings:booking_detail", args=[amendment.booking_id]),
                "classNames": ["amendment-pending", *([] if can_open else ["masked"])],
                "extendedProps": {
                    "status": "amendment_pending",
                    "room": proposed_room.code,
                    "amendment": amendment_ref(amendment),
                },
            }
        )
    selected_room = None
    if request.GET.get("room"):
        selected_room = Resource.objects.filter(code=request.GET["room"], resource_type=Resource.Type.ROOM).first()
    blackouts = Blackout.objects.filter(start_at__lt=end, end_at__gt=start).prefetch_related("rooms")
    for blackout in blackouts:
        if selected_room and not blackout.applies_to(selected_room):
            continue
        if request.GET.get("building") and blackout.scope != Blackout.Scope.ALL:
            building_rooms = Resource.objects.filter(
                resource_type=Resource.Type.ROOM,
                building=request.GET["building"],
            )
            if not any(blackout.applies_to(room) for room in building_rooms):
                continue
        events.append(
            {
                "title": f"{blackout.title} ({blackout.get_scope_display()})",
                "start": blackout.start_at.isoformat(),
                "end": blackout.end_at.isoformat(),
                "display": "background",
                "classNames": ["blackout-event"],
            }
        )
    if selected_room:
        for outage in active_outages(selected_room, start, end):
            events.append(
                {
                    "title": f"งดใช้: {outage.reason}",
                    "start": outage.start_at.isoformat(),
                    "end": outage.end_at.isoformat(),
                    "display": "background",
                    "classNames": ["outage-event"],
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
                audit(request.user, "bookings.booking", booking.pk, "booking_created", after=model_snapshot(booking))
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
                audit(request.user, "bookings.booking", booking.pk, "booking_created", after=model_snapshot(booking))
                notify_submitted(booking)
                messages.success(request, "ส่งคำขอจองห้องแล้ว")
                return redirect("bookings:booking_detail", id=booking.id)
    else:
        form = BookingForm(user=request.user, room=room, instance=booking, initial=_initial_from_query(request))
    return render(request, "bookings/book_form.html", {"form": form, "room": room})


def _series_form_booking(form, room, user):
    booking = form.save(commit=False)
    booking.room = room
    booking.requester = user
    booking._series_equipment = list(form.cleaned_data.get("equipment", []))
    return booking


@login_required
@require_POST
def series_preview(request, code):
    room = get_object_or_404(Resource.objects.select_related("rule"), code=code, resource_type=Resource.Type.ROOM)
    booking = Booking(room=room, requester=request.user, unit=request.user.unit)
    form = BookingForm(request.POST, user=request.user, room=room, instance=booking)
    if not form.is_valid() or not form.cleaned_data.get("is_series"):
        if form.is_valid():
            form.add_error("is_series", "กรุณาเลือกจองเป็นชุด")
        return render(request, "bookings/book_form.html", {"form": form, "room": room}, status=400)
    booking = _series_form_booking(form, room, request.user)
    try:
        preview = preview_series(room, form.series_params(), booking, request.user)
    except ValidationError as exc:
        for message in exc.messages:
            form.add_error(None, message)
        return render(request, "bookings/book_form.html", {"form": form, "room": room}, status=400)
    return render(
        request,
        "bookings/series_preview.html",
        {"form": form, "room": room, "booking": booking, "preview": preview},
    )


@login_required
@require_POST
def series_create(request, code):
    room = get_object_or_404(Resource.objects.select_related("rule"), code=code, resource_type=Resource.Type.ROOM)
    booking = Booking(room=room, requester=request.user, unit=request.user.unit)
    form = BookingForm(request.POST, user=request.user, room=room, instance=booking)
    if not form.is_valid() or not form.cleaned_data.get("is_series"):
        messages.error(request, "ข้อมูลชุดการจองไม่ครบ กรุณาตรวจสอบอีกครั้ง")
        return render(request, "bookings/book_form.html", {"form": form, "room": room}, status=400)
    booking = _series_form_booking(form, room, request.user)
    try:
        params = form.series_params()
        params["preview_free_dates"] = request.POST.getlist("_preview_free_dates")
        series = create_series(room, params, booking, request.user)
    except ValidationError as exc:
        for message in exc.messages:
            form.add_error(None, message)
        return render(request, "bookings/book_form.html", {"form": form, "room": room}, status=400)
    messages.success(
        request,
        f"สร้างชุดการจองแล้ว {series.occurrences.count()} ครั้ง · ข้าม {series.skips.count()} ครั้ง",
    )
    return redirect("bookings:series_detail", id=series.pk)


@login_required
def series_detail(request, id):
    series = get_object_or_404(
        BookingSeries.objects.select_related("room", "room__rule", "created_by", "unit"),
        pk=id,
    )
    occurrences = list(
        series.occurrences.select_related("room", "requester", "unit").prefetch_related("equipment").order_by("start_at")
    )
    if not occurrences:
        raise Http404
    first = occurrences[0]
    if not (can_view_details(request.user, first) or can_decide(request.user, first)):
        raise PermissionDenied("คุณไม่มีสิทธิ์ดูชุดการจองนี้")
    counts = {}
    for booking in occurrences:
        counts[booking.request_status] = counts.get(booking.request_status, 0) + 1
    return render(
        request,
        "bookings/series_detail.html",
        {
            "series": series,
            "series_code": series_ref(series),
            "occurrences": occurrences,
            "skips": series.skips.all(),
            "counts": counts,
            "can_cancel": series.created_by_id == request.user.pk or request.user.is_superuser,
            "now": timezone.now(),
            "title": first.title,
        },
    )


@login_required
@require_POST
def series_cancel_remaining(request, id):
    series = get_object_or_404(BookingSeries, pk=id)
    try:
        result = cancel_remaining(series, request.user)
    except PermissionError as exc:
        messages.error(request, str(exc))
    else:
        text = f"ยกเลิกครั้งที่เหลือแล้ว {result['cancelled']} ครั้ง"
        if result["skipped"]:
            text += f" · ข้าม {len(result['skipped'])} ครั้งที่พ้นเส้นตาย"
        messages.success(request, text)
    return redirect("bookings:series_detail", id=series.pk)


@login_required
def booking_detail(request, id):
    booking = get_object_or_404(_booking_queryset(), id=id)
    pending_amendment = (
        booking.amendments.filter(status=BookingAmendment.Status.PENDING)
        .select_related("proposed_room", "submitted_by")
        .prefetch_related("proposed_equipment")
        .first()
    )
    full_details = can_view_details(request.user, booking)
    approval_access = can_decide(request.user, booking) or bool(
        pending_amendment and can_decide(request.user, pending_amendment)
    )
    can_approve = booking.request_status == Booking.RequestStatus.PENDING and approval_access and not booking.series_id
    if approval_access:
        full_details = True
    if not full_details:
        return render(request, "bookings/booking_masked.html", {"booking": booking})
    owner = booking.requester_id == request.user.pk or request.user.is_superuser
    fields = editable_fields(booking) if owner else set()
    if pending_amendment:
        pending_amendment.display_ref = amendment_ref(pending_amendment)
        pending_amendment.new_room = pending_amendment.proposed_room or booking.room
        pending_amendment.new_start_at = pending_amendment.proposed_start_at or booking.start_at
        pending_amendment.new_end_at = pending_amendment.proposed_end_at or booking.end_at
    preemption = booking.preemption_as_displaced.select_related(
        "incoming", "replacement", "replacement__room", "ordered_by"
    ).first()
    return render(
        request,
        "bookings/booking_detail.html",
        {
            "booking": booking,
            "can_edit": bool(fields),
            "can_amend": (
                owner
                and booking.request_status == Booking.RequestStatus.APPROVED
                and booking.usage_status == Booking.UsageStatus.UPCOMING
                and not self_service_message(booking)
                and pending_amendment is None
            ),
            "pending_amendment": pending_amendment,
            "preemption": preemption,
            "can_preempt": can_preempt(request.user, booking),
            "can_acknowledge": bool(
                preemption
                and preemption.acknowledged_at is None
                and not preemption.deemed_acknowledged
                and booking.requester_id == request.user.pk
            ),
            "can_cancel": owner and not self_service_message(booking) and booking.request_status not in {
                Booking.RequestStatus.CANCELLED,
                Booking.RequestStatus.REJECTED,
                Booking.RequestStatus.EXPIRED,
            } and booking.usage_status == Booking.UsageStatus.UPCOMING,
            "deadline_message": self_service_message(booking) if owner else "",
            "can_approve": can_approve,
            "approval_history": booking.approvals.select_related("acted_by", "on_behalf_of").all(),
            "rejection_reasons": recent_rejection_reasons(request.user) if can_approve else [],
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
            before = model_snapshot(booking)
            booking = form.save()
            booking.revision += 1
            booking.save(update_fields=["revision", "updated_at"])
            audit(request.user, "bookings.booking", booking.pk, "booking_updated", before=before, after=model_snapshot(booking))
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
def booking_amend(request, id):
    booking = get_object_or_404(_booking_queryset(), id=id)
    if booking.requester_id != request.user.pk and not request.user.is_superuser:
        raise PermissionDenied("คุณไม่มีสิทธิ์ขอแก้ไขการจองนี้")
    form = AmendmentForm(request.POST or None, booking=booking, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            amendment = submit_amendment(booking, request.user, form.proposed())
        except (BookingConflict, PermissionError, ValueError, ValidationError) as exc:
            text = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
            form.add_error(None, text)
        else:
            if amendment.status == BookingAmendment.Status.APPROVED:
                messages.success(request, "การแก้ไขมีผลทันทีแล้ว")
            else:
                messages.success(request, f"ส่งคำขอแก้ไข {amendment_ref(amendment)} แล้ว")
            return redirect("bookings:booking_detail", id=booking.pk)
    proposed = form.proposed() if form.is_bound and form.is_valid() else {
        "room": booking.room,
        "has_external": booking.has_external_attendees,
    }
    policy = evaluate_amendment_policy(booking, proposed)
    return render(
        request,
        "bookings/amend_form.html",
        {
            "booking": booking,
            "form": form,
            "policy_required": policy == ResourceRule.ApprovalPolicy.REQUIRED,
        },
    )


@login_required
@require_POST
def amendment_withdraw(request, id):
    amendment = get_object_or_404(BookingAmendment.objects.select_related("booking", "submitted_by"), pk=id)
    try:
        withdraw_amendment(amendment, request.user, request.POST.get("reason", ""))
    except (PermissionError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "ถอนคำขอแก้ไขและคืนช่วงเวลาปลายทางแล้ว")
    return redirect("bookings:booking_detail", id=amendment.booking_id)


@login_required
def booking_preempt(request, id):
    booking = get_object_or_404(_booking_queryset(), id=id)
    if not can_preempt(request.user, booking):
        raise PermissionDenied("คุณไม่มีสิทธิ์บังคับย้ายการจองนี้")
    options = replacement_options(booking, request.user)
    form = PreemptionForm(request.POST or None, booking=booking, actor=request.user, options=options)
    if request.method == "POST" and form.is_valid():
        try:
            execute_preemption(
                booking,
                request.user,
                form.cleaned_data["reason"],
                form.cleaned_data["reference_no"],
                form.incoming_data(),
                form.cleaned_data["replacement_room_object"],
            )
        except (BookingConflict, PermissionError, ValueError, ValidationError) as exc:
            text = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
            form.add_error(None, text)
        else:
            messages.success(request, "บังคับย้ายและแจ้งผู้เกี่ยวข้องแล้ว")
            return redirect("bookings:booking_detail", id=booking.pk)
    return render(
        request,
        "bookings/preempt_form.html",
        {"booking": booking, "form": form, "options": options},
    )


@login_required
@require_POST
def preemption_acknowledge(request, id):
    preemption = get_object_or_404(Preemption.objects.select_related("displaced", "ordered_by"), pk=id)
    try:
        acknowledge(preemption, request.user)
    except PermissionError as exc:
        raise PermissionDenied(str(exc))
    messages.success(request, "บันทึกการรับทราบแล้ว")
    return redirect("bookings:booking_detail", id=preemption.displaced_id)


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
        notify_submitted(booking)
        messages.success(request, "ส่งคำขอจองห้องแล้ว")
    return redirect("bookings:booking_detail", id=booking.id)


@login_required
@require_POST
def booking_delete_draft(request, id):
    booking = get_object_or_404(Booking, id=id, requester=request.user)
    if booking.request_status != Booking.RequestStatus.DRAFT:
        raise Http404
    before = model_snapshot(booking)
    booking.delete()
    audit(request.user, "bookings.booking", id, "booking_draft_deleted", before=before)
    messages.success(request, "ลบร่างแล้ว")
    return redirect("bookings:my_bookings")


@login_required
def my_bookings(request):
    now = timezone.now()
    bookings = _booking_queryset().filter(requester=request.user, series__isnull=True)
    groups = {
        "upcoming": bookings.filter(start_at__gte=now).exclude(request_status__in=[Booking.RequestStatus.DRAFT, Booking.RequestStatus.CANCELLED, Booking.RequestStatus.REJECTED]),
        "drafts": bookings.filter(request_status=Booking.RequestStatus.DRAFT),
        "past": bookings.filter(end_at__lt=now).exclude(request_status__in=[Booking.RequestStatus.CANCELLED, Booking.RequestStatus.REJECTED]),
        "closed": bookings.filter(request_status__in=[Booking.RequestStatus.CANCELLED, Booking.RequestStatus.REJECTED, Booking.RequestStatus.EXPIRED]),
    }
    tab = request.GET.get("tab", "upcoming")
    if tab not in groups:
        tab = "upcoming"
    series_items = list(
        BookingSeries.objects.filter(created_by=request.user)
        .select_related("room")
        .prefetch_related("occurrences", "skips")
    )
    for series in series_items:
        occurrences = list(series.occurrences.all())
        series.display_ref = series_ref(series)
        series.display_total = len(occurrences)
        series.display_next = min((item.start_at for item in occurrences if item.start_at >= now), default=None)
    return render(
        request,
        "bookings/my_bookings.html",
        {"groups": groups, "tab": tab, "bookings": groups[tab], "series_items": series_items},
    )

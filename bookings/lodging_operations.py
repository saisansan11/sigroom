"""Staff workspace presentation; allocation rules remain in lodging_services."""
from datetime import datetime, time, timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.db.models import Case, IntegerField, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .lodging_models import CourseLodgingCohort, CourseLodgingRelease, PublicLodgingAccess
from .lodging_services import (
    assign_lodging_bed,
    can_access_lodging_management,
    can_create_cohort,
    can_manage_cohort,
    cohort_hold_range,
    cohort_self_booking_status,
    move_lodging_bed,
    nearby_public_lodging_dates,
    public_lodging_rooms as service_public_lodging_rooms,
    available_public_lodging_rooms,
    release_lodging_reservation,
    request_general_lodging,
    set_cohort_self_booking,
    update_cohort_allocation,
)
from .models import BookingResource
from .services import BookingConflict
from resources.models import Resource
from audit.context import client_ip_is_trusted, request_ip


class AssignmentForm(forms.Form):
    room_id = forms.ChoiceField(label="ห้องพัก")
    bed_number = forms.ChoiceField(label="เตียง")
    rank = forms.CharField(label="ยศ", max_length=50, widget=forms.TextInput(attrs={"list": "staff-ranks"}))
    full_name = forms.CharField(label="ชื่อ-นามสกุล", max_length=150)
    origin_unit = forms.CharField(label="หน่วยต้นสังกัด", max_length=150, widget=forms.TextInput(attrs={"list": "staff-units"}))
    phone = forms.CharField(label="เบอร์โทรศัพท์", max_length=30, widget=forms.TextInput(attrs={"inputmode": "tel"}))
    note = forms.CharField(label="หมายเหตุ", max_length=200, required=False)

    def __init__(self, *args, cohort, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["room_id"].choices = [(str(r.pk), r.code) for r in cohort.rooms.all().order_by("code")]
        self.fields["bed_number"].choices = [(str(n), str(n)) for n in range(1, cohort.beds_per_room + 1)]


class MoveBedForm(forms.Form):
    target = forms.ChoiceField(label="ย้ายไปห้อง / เตียง")

    def __init__(self, *args, cohort, student, **kwargs):
        super().__init__(*args, **kwargs)
        occupied = set(
            cohort.students.exclude(pk=student.pk).values_list("room_id", "bed_number")
        )
        choices = []
        for room in cohort.rooms.filter(status=Resource.Status.ACTIVE).order_by("floor", "code"):
            for bed_number in range(1, cohort.beds_per_room + 1):
                if (room.pk, bed_number) in occupied:
                    continue
                if room.pk == student.room_id and bed_number == student.bed_number:
                    continue
                choices.append((f"{room.pk}:{bed_number}", f"{room.code} · เตียง {bed_number}"))
        self.fields["target"].choices = choices

    def clean_target(self):
        raw = self.cleaned_data["target"]
        room_id, separator, bed_number = raw.partition(":")
        if not separator:
            raise ValidationError("ปลายทางไม่ถูกต้อง")
        try:
            return room_id, int(bed_number)
        except (TypeError, ValueError) as exc:
            raise ValidationError("ปลายทางไม่ถูกต้อง") from exc


def public_lodging_rooms():
    """Backward-compatible import point; business inventory selection lives in lodging_services."""
    return service_public_lodging_rooms()


class PublicRoomChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, attendees=1, **kwargs):
        self.attendees = attendees
        super().__init__(*args, **kwargs)

    def label_from_instance(self, obj):
        capacity = int(obj.capacity or 0)
        if capacity:
            suffix = f" · รองรับ {capacity} คน"
            if capacity < self.attendees:
                suffix += " · เกินความจุ"
        else:
            suffix = " · ไม่ระบุความจุ"
        return f"{obj.code}{suffix}"


class GeneralRequestForm(forms.Form):
    check_in = forms.DateField(label="วันเข้าพัก (14:00 น.)", widget=forms.DateInput(attrs={"type": "date"}))
    check_out = forms.DateField(label="วันออก (12:00 น.)", widget=forms.DateInput(attrs={"type": "date"}))
    attendees = forms.IntegerField(label="จำนวนผู้พัก", min_value=1, max_value=20, initial=1, required=False)
    guest_name = forms.CharField(label="ชื่อผู้เข้าพัก / ผู้ติดต่อ", max_length=200)
    phone = forms.CharField(label="เบอร์โทรติดต่อ", max_length=30, widget=forms.TextInput(attrs={"inputmode": "tel"}))
    room = PublicRoomChoiceField(label="ห้องที่ระบบเสนอ", queryset=Resource.objects.none())
    note = forms.CharField(label="หมายเหตุ", required=False, max_length=1000,
                           widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, selection_data=None, preferred_room_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        source = self.data if self.is_bound else (selection_data or {})
        initial = self.initial or {}
        raw_check_in = source.get("check_in") or initial.get("check_in")
        raw_check_out = source.get("check_out") or initial.get("check_out")
        raw_attendees = source.get("attendees") or initial.get("attendees") or 1

        # Preserve the historical form contract for registry/admin callers that
        # instantiate the form only to inspect the public lodging inventory.
        # The public request view always supplies dates, so the task-first flow
        # still filters rooms by the requested stay before presenting choices.
        if not raw_check_in or not raw_check_out:
            self.fields["room"].queryset = public_lodging_rooms()
            self.fields["room"].attendees = 1
            return

        try:
            check_in = forms.DateField().clean(raw_check_in)
            check_out = forms.DateField().clean(raw_check_out)
            attendees = int(raw_attendees)
        except (ValidationError, TypeError, ValueError):
            return
        if attendees < 1 or check_out <= check_in:
            return

        rooms = available_public_lodging_rooms(
            check_in=check_in,
            check_out=check_out,
            attendees=attendees,
        )
        ids = [room.pk for room in rooms]
        self.available_room_ids = set(ids)

        # A bound POST must be allowed to carry its selected public room through form
        # validation even if the room became unavailable after the page loaded. The
        # service/database then re-checks and returns the safe conflict/duplicate message.
        validation_ids = list(ids)
        if self.is_bound and source.get("room"):
            try:
                posted_pk = int(source.get("room"))
            except (TypeError, ValueError):
                posted_pk = None
            if posted_pk and posted_pk not in validation_ids and public_lodging_rooms().filter(pk=posted_pk).exists():
                validation_ids.append(posted_pk)

        if validation_ids:
            ordering = Case(
                *[When(pk=pk, then=position) for position, pk in enumerate(validation_ids)],
                output_field=IntegerField(),
            )
            queryset = public_lodging_rooms().filter(pk__in=validation_ids).order_by(ordering)
        else:
            queryset = Resource.objects.none()
        self.fields["room"].queryset = queryset
        self.fields["room"].attendees = attendees

        selected_pk = None
        if preferred_room_id:
            try:
                preferred_pk = int(preferred_room_id)
            except (TypeError, ValueError):
                preferred_pk = None
            if preferred_pk in ids:
                selected_pk = preferred_pk
        if selected_pk is None and ids:
            selected_pk = ids[0]
        if selected_pk is not None and not self.is_bound:
            self.initial["room"] = selected_pk

    def clean_attendees(self):
        return self.cleaned_data.get("attendees") or 1

    def clean(self):
        cleaned = super().clean()
        check_in = cleaned.get("check_in")
        check_out = cleaned.get("check_out")
        if check_in and check_in < timezone.localdate():
            self.add_error("check_in", "วันเข้าพักต้องไม่เป็นวันที่ผ่านมาแล้ว")
        if check_in and check_out and check_out <= check_in:
            self.add_error("check_out", "วันออกต้องอยู่หลังวันเข้า")
        return cleaned


def _parse_local_datetime(value, label):
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{label}ไม่ถูกต้อง") from exc
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _assignment_is_open(cohort):
    return (
        cohort.allocation_status == CourseLodgingCohort.AllocationStatus.ALLOCATED
        and cohort.check_out_date >= timezone.localdate()
    )


def _assignment_selection(cohort, room_id, bed_number):
    """Return a currently free cohort bed for presentation-only preselection."""
    if not _assignment_is_open(cohort) or not room_id or not bed_number:
        return None
    try:
        bed_number = int(bed_number)
    except (TypeError, ValueError):
        return None
    if not 1 <= bed_number <= cohort.beds_per_room:
        return None
    try:
        room = cohort.rooms.filter(pk=room_id, status=Resource.Status.ACTIVE).first()
    except (TypeError, ValueError, ValidationError):
        return None
    if room is None or cohort.students.filter(room=room, bed_number=bed_number).exists():
        return None
    return {"room": room, "bed_number": bed_number}


def _room_filter(value):
    return value if value in {"all", "free", "full"} else "all"


def _arrival_filter(value):
    return value if value in {"all", "pending", "checked_in"} else "all"


def _public_pending_requests(user):
    from approvals.services import pending_for

    pending = [
        item for item in pending_for(user)
        if not getattr(item, "is_amendment_card", False) and not getattr(item, "is_series_card", False)
    ]
    booking_ids = [item.pk for item in pending]
    public_ids = set(
        PublicLodgingAccess.objects.filter(booking_id__in=booking_ids)
        .values_list("booking_id", flat=True)
    )
    return [item for item in pending if item.pk in public_ids]


def _cohort_operations_card(cohort):
    rooms = list(cohort.rooms.all())
    students = list(cohort.students.all())
    capacity = len(rooms) * cohort.beds_per_room
    status, status_message = cohort_self_booking_status(cohort)
    return {
        "cohort": cohort,
        "booking_status": status,
        "booking_status_message": status_message,
        "capacity": capacity,
        "assigned": len(students),
        "free_beds": max(0, capacity - len(students)),
        "pending_arrivals": sum(1 for student in students if not student.checked_in_at),
        "checked_in": sum(1 for student in students if student.checked_in_at),
        "no_show": sum(
            1
            for release in cohort.releases.all()
            if release.outcome == CourseLodgingRelease.Outcome.NO_SHOW
        ),
        "can_toggle_booking": (
            cohort.allocation_status == CourseLodgingCohort.AllocationStatus.ALLOCATED
            and cohort.check_out_date >= timezone.localdate()
        ),
    }


def _operations_summary(cards, public_pending):
    active_cards = [
        card for card in cards
        if card["cohort"].allocation_status == CourseLodgingCohort.AllocationStatus.ALLOCATED
        and card["cohort"].check_out_date >= timezone.localdate()
    ]
    return {
        "public_pending": len(public_pending),
        "open_courses": sum(1 for card in active_cards if card["booking_status"] == "open"),
        "assigned": sum(card["assigned"] for card in active_cards),
        "free_beds": sum(card["free_beds"] for card in active_cards),
        "pending_arrivals": sum(card["pending_arrivals"] for card in active_cards),
        "no_show": sum(card["no_show"] for card in cards),
    }


def _general_request_initial(request):
    today = timezone.localdate()
    initial = {
        "check_in": today,
        "check_out": today + timedelta(days=1),
        "attendees": 1,
    }
    if getattr(request.user, "is_authenticated", False):
        initial.update({
            "guest_name": request.user.display_name,
            "phone": getattr(request.user, "phone", ""),
        })
    for key in ("check_in", "check_out", "attendees"):
        if request.GET.get(key):
            initial[key] = request.GET[key]
    if request.GET.get("attendees_delta") in {"-1", "1"}:
        try:
            current = int(initial.get("attendees") or 1)
            delta = int(request.GET["attendees_delta"])
        except (TypeError, ValueError):
            current, delta = 1, 0
        initial["attendees"] = min(20, max(1, current + delta))
    return initial


def _general_room_context(form):
    rooms = list(form.fields["room"].queryset)
    available_ids = getattr(form, "available_room_ids", {room.pk for room in rooms})
    available_rooms = [room for room in rooms if room.pk in available_ids]
    selected = None
    selected_value = form["room"].value()
    if selected_value:
        selected = next((room for room in available_rooms if str(room.pk) == str(selected_value)), None)
    if selected is None and available_rooms:
        selected = available_rooms[0]
    return {"suggested_room": selected, "available_room_count": len(available_rooms)}


@require_GET
def general_request_rooms(request):
    """HTMX/public room suggestion endpoint; bounded to a 60-day scan horizon and exposes no PII."""
    try:
        check_in = forms.DateField().clean(request.GET.get("check_in"))
        check_out = forms.DateField().clean(request.GET.get("check_out"))
        attendees = int(request.GET.get("attendees") or 1)
    except (ValidationError, TypeError, ValueError):
        return render(
            request,
            "lodging/partials/general_request_rooms.html",
            {"room_error": "กรุณาตรวจวันเข้าพัก วันออก และจำนวนผู้พัก"},
            status=400,
        )
    today = timezone.localdate()
    horizon = today + timedelta(days=60)
    if check_in < today or check_in > horizon or check_out > horizon or check_out <= check_in or attendees < 1 or attendees > 20:
        return render(
            request,
            "lodging/partials/general_request_rooms.html",
            {"room_error": "ค้นหาห้องได้ตั้งแต่วันนี้ถึง 60 วันข้างหน้า และวันออกต้องอยู่หลังวันเข้า"},
            status=400,
        )

    form = GeneralRequestForm(
        initial={"check_in": check_in, "check_out": check_out, "attendees": attendees},
        selection_data=request.GET,
        preferred_room_id=request.GET.get("room_id") or request.GET.get("room"),
    )
    context = {"form": form, **_general_room_context(form)}
    if context["available_room_count"] == 0:
        context["nearby_dates"] = nearby_public_lodging_dates(
            check_in=check_in,
            check_out=check_out,
            attendees=attendees,
        )
    response = render(request, "lodging/partials/general_request_rooms.html", context)
    response["Cache-Control"] = "no-store"
    return response


def general_request(request):
    initial = _general_request_initial(request)
    preferred_room_id = request.GET.get("room_id") or request.GET.get("room") or ""
    selection_data = initial if request.method == "GET" else None
    form = GeneralRequestForm(
        request.POST if request.method == "POST" else None,
        initial=initial,
        selection_data=selection_data,
        preferred_room_id=preferred_room_id,
    )
    room_context = _general_room_context(form)
    if preferred_room_id and room_context["suggested_room"] is None:
        messages.warning(request, "ห้องที่เลือกไม่ว่างในวันที่ระบุ ระบบจะแสดงห้องอื่นที่พร้อมแทน")

    if request.method == "POST" and form.is_valid():
        authenticated = bool(getattr(request.user, "is_authenticated", False))
        client_key = ""
        if not authenticated:
            client_ip = request_ip(request) if client_ip_is_trusted() else ""
            if client_ip:
                client_key = f"ip:{client_ip}"
            else:
                if request.session.session_key is None:
                    request.session.create()
                client_key = request.session.session_key or ""
        try:
            booking = request_general_lodging(
                actor=request.user if authenticated else None,
                client_key=client_key,
                **form.cleaned_data,
            )
        except (ValidationError, BookingConflict) as exc:
            form.add_error(None, " · ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
        else:
            messages.success(request, "ส่งคำขอแล้ว กรุณาเก็บลิงก์นี้ไว้เพื่อตรวจสถานะ")
            return redirect("bookings:lodging_general_request_status", token=booking.public_lodging_access.pk)

    context = {"form": form, **room_context}
    if room_context["available_room_count"] == 0:
        try:
            check_in = forms.DateField().clean(form["check_in"].value())
            check_out = forms.DateField().clean(form["check_out"].value())
            attendees = int(form["attendees"].value() or 1)
        except (ValidationError, TypeError, ValueError):
            pass
        else:
            context["nearby_dates"] = nearby_public_lodging_dates(
                check_in=check_in,
                check_out=check_out,
                attendees=attendees,
            )
            context["nights"] = max(1, (check_out - check_in).days)
    else:
        try:
            check_in = forms.DateField().clean(form["check_in"].value())
            check_out = forms.DateField().clean(form["check_out"].value())
            context["nights"] = max(1, (check_out - check_in).days)
        except (ValidationError, TypeError, ValueError):
            pass
    response = render(request, "lodging/general_request.html", context)
    response["Cache-Control"] = "no-store"
    return response


@login_required
def lodging_workspace(request):
    if not can_access_lodging_management(request.user):
        raise PermissionDenied
    cohorts = (
        CourseLodgingCohort.objects.all()
        .prefetch_related("rooms", "students", "releases")
        .order_by("-check_in_date")
    )
    if not (request.user.is_superuser or request.user.has_perm("bookings.change_courselodgingcohort")):
        cohorts = cohorts.filter(supervisor=request.user)
    cohort_cards = [_cohort_operations_card(item) for item in cohorts]
    public_pending_requests = _public_pending_requests(request.user)
    operations_summary = _operations_summary(cohort_cards, public_pending_requests)
    can_manage_course_operations = bool(
        can_create_cohort(request.user)
        or request.user.has_perm("bookings.change_courselodgingcohort")
        or CourseLodgingCohort.objects.filter(supervisor=request.user).exists()
    )

    slug = request.GET.get("cohort")
    if slug:
        cohort = get_object_or_404(cohorts, slug=slug)
    else:
        cohort = cohort_cards[0]["cohort"] if cohort_cards else None
    room_filter = _room_filter(request.GET.get("room_filter"))
    arrival_filter = _arrival_filter(request.GET.get("arrival_filter"))
    form, rooms, available_rooms, selected_assignment, assignment_open = None, [], [], None, False
    move_student, move_form = None, None
    cohort_booking_state, cohort_booking_message = "unavailable", "ยังไม่มีหลักสูตรที่เลือก"
    occupancy = {
        "capacity": 0,
        "assigned": 0,
        "free_beds": 0,
        "checked_in": 0,
        "rooms_total": 0,
        "rooms_free": 0,
        "rooms_full": 0,
    }
    arrival = {"pending": 0, "checked_in": 0}
    if cohort:
        if not can_manage_cohort(request.user, cohort):
            raise PermissionDenied
        assignment_open = _assignment_is_open(cohort)
        cohort_booking_state, cohort_booking_message = cohort_self_booking_status(cohort)
        action = request.POST.get("action", "") if request.method == "POST" else ""

        if action == "booking_toggle":
            requested_state = request.POST.get("booking_state", "")
            if requested_state not in {"open", "closed"}:
                messages.error(request, "สถานะรับจองไม่ถูกต้อง")
            else:
                try:
                    set_cohort_self_booking(
                        cohort=cohort,
                        actor=request.user,
                        enabled=requested_state == "open",
                    )
                except (PermissionDenied, ValidationError, ValueError, IntegrityError) as exc:
                    text = " · ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                    messages.error(request, text)
                else:
                    messages.success(
                        request,
                        "เปิดรับจองสำหรับนักเรียนแล้ว" if requested_state == "open" else "ปิดรับจองสำหรับนักเรียนแล้ว",
                    )
                    return redirect(f"{request.path}?cohort={cohort.slug}")

        if action == "release_student":
            student_id = request.POST.get("student_id", "")
            outcome = request.POST.get("outcome", "")
            target_student = cohort.students.filter(pk=student_id).first()
            if target_student is None:
                messages.error(request, "ไม่พบผู้เข้าพักที่ต้องการดำเนินการ")
            else:
                try:
                    release_lodging_reservation(
                        student=target_student,
                        outcome=outcome,
                        actor=request.user,
                        reason=request.POST.get("reason", ""),
                    )
                except (PermissionDenied, ValidationError, ValueError, IntegrityError) as exc:
                    text = " · ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                    messages.error(request, text)
                else:
                    if outcome == CourseLodgingRelease.Outcome.NO_SHOW:
                        messages.success(request, "บันทึกไม่มารายงานตัวและคืนเตียงแล้ว")
                    elif outcome == CourseLodgingRelease.Outcome.CHECKED_OUT:
                        messages.success(request, "บันทึกออกจากที่พักและคืนเตียงแล้ว")
                    else:
                        messages.success(request, "ยกเลิกการจองและคืนเตียงแล้ว")
                    return redirect(f"{request.path}?cohort={cohort.slug}#room-board")

        allocating = action == "allocation"
        if allocating:
            try:
                is_active = request.POST.get("is_active") == "on"
                booking_open_at = _parse_local_datetime(request.POST.get("booking_open_at"), "เวลาเปิดรับจอง")
                booking_close_at = _parse_local_datetime(request.POST.get("booking_close_at"), "เวลาปิดรับจอง")
                if is_active and not booking_open_at and not booking_close_at:
                    booking_open_at = timezone.now()
                    booking_close_at = timezone.make_aware(
                        datetime.combine(cohort.check_in_date, time(23, 59)),
                        timezone.get_current_timezone(),
                    )
                elif is_active and (not booking_open_at or not booking_close_at):
                    raise ValidationError("กรุณากำหนดทั้งเวลาเปิดและปิดรับจอง")
                update_cohort_allocation(
                    cohort=cohort,
                    rooms=Resource.objects.filter(pk__in=request.POST.getlist("rooms")),
                    check_in_date=cohort.check_in_date,
                    check_out_date=cohort.check_out_date,
                    allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
                    is_active=is_active,
                    beds_per_room=cohort.beds_per_room,
                    booking_open_at=booking_open_at,
                    booking_close_at=booking_close_at,
                    actor=request.user,
                )
            except (ValidationError, ValueError, IntegrityError) as exc:
                messages.error(
                    request,
                    " · ".join(exc.messages) if isinstance(exc, ValidationError) else "กรุณาตรวจห้องที่เลือกอีกครั้ง",
                )
            else:
                messages.success(request, "บันทึกการจัดสรรห้องและสถานะรับจองแล้ว")
                return redirect(request.get_full_path())

        move_id = request.POST.get("student_id") if action == "move_bed" else request.GET.get("move")
        if move_id:
            try:
                move_student = cohort.students.select_related("room").filter(pk=move_id).first()
            except (ValueError, ValidationError):
                move_student = None
        if action == "move_bed" and move_student is None:
            messages.error(request, "ไม่พบผู้เข้าพักที่ต้องการย้าย")
        if move_student is not None:
            move_form = MoveBedForm(
                request.POST if action == "move_bed" else None,
                cohort=cohort,
                student=move_student,
            )
            if action == "move_bed" and move_form.is_valid():
                room_id, bed_number = move_form.cleaned_data["target"]
                try:
                    move_lodging_bed(
                        student=move_student,
                        room_id=room_id,
                        bed_number=bed_number,
                        actor=request.user,
                    )
                except (PermissionDenied, ValidationError, ValueError, IntegrityError) as exc:
                    text = " · ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                    move_form.add_error(None, text)
                else:
                    messages.success(request, f"ย้าย {move_student.rank} {move_student.full_name} เรียบร้อยแล้ว")
                    return redirect(f"{request.path}?cohort={cohort.slug}#room-board")

        if request.method == "GET":
            selected_assignment = _assignment_selection(cohort, request.GET.get("room"), request.GET.get("bed"))
        initial = None
        if selected_assignment:
            initial = {
                "room_id": str(selected_assignment["room"].pk),
                "bed_number": str(selected_assignment["bed_number"]),
            }
        assignment_post = request.POST if request.method == "POST" and action in {"", "assign"} else None
        form = AssignmentForm(assignment_post, cohort=cohort, initial=initial)
        if request.method == "POST" and action in {"", "assign"} and form.is_valid():
            try:
                assign_lodging_bed(cohort=cohort, actor=request.user, **form.cleaned_data)
            except (ValidationError, IntegrityError) as exc:
                form.add_error(
                    None,
                    " · ".join(exc.messages) if isinstance(exc, ValidationError) else "เตียงถูกจองแล้ว กรุณาตรวจสอบอีกครั้ง",
                )
            else:
                messages.success(request, "จัดผู้เข้าพักเรียบร้อยแล้ว")
                return redirect(request.get_full_path())

        students = list(cohort.students.select_related("room").order_by("bed_number"))
        all_rooms = []
        for room in cohort.rooms.order_by("floor", "code"):
            occupants = {s.bed_number: s for s in students if s.room_id == room.pk}
            free = cohort.beds_per_room - len(occupants)
            pending_arrivals = sum(1 for student in occupants.values() if not student.checked_in_at)
            checked_arrivals = sum(1 for student in occupants.values() if student.checked_in_at)
            all_rooms.append(
                {
                    "room": room,
                    "free": free,
                    "assignable": assignment_open and room.status == Resource.Status.ACTIVE,
                    "pending_arrivals": pending_arrivals,
                    "checked_arrivals": checked_arrivals,
                    "beds": [
                        {"number": n, "student": occupants.get(n)}
                        for n in range(1, cohort.beds_per_room + 1)
                    ],
                }
            )
        occupancy = {
            "capacity": len(all_rooms) * cohort.beds_per_room,
            "assigned": len(students),
            "free_beds": max(0, len(all_rooms) * cohort.beds_per_room - len(students)),
            "checked_in": sum(1 for student in students if student.checked_in_at),
            "rooms_total": len(all_rooms),
            "rooms_free": sum(1 for item in all_rooms if item["free"] > 0),
            "rooms_full": sum(1 for item in all_rooms if item["free"] == 0),
        }
        arrival = {
            "pending": sum(1 for student in students if not student.checked_in_at),
            "checked_in": sum(1 for student in students if student.checked_in_at),
        }
        if room_filter == "free":
            rooms = [item for item in all_rooms if item["free"] > 0]
        elif room_filter == "full":
            rooms = [item for item in all_rooms if item["free"] == 0]
        else:
            rooms = all_rooms
        if arrival_filter == "pending":
            rooms = [item for item in rooms if item["pending_arrivals"] > 0]
        elif arrival_filter == "checked_in":
            rooms = [item for item in rooms if item["checked_arrivals"] > 0]
        selected = set(cohort.rooms.values_list("pk", flat=True))
        hold = cohort_hold_range(cohort.check_in_date, cohort.check_out_date)
        blocked = set(
            BookingResource.objects.filter(released_at__isnull=True, hold__overlap=hold)
            .values_list("resource_id", flat=True)
        )
        blocked.update(
            CourseLodgingCohort.objects.filter(
                allocation_status="allocated",
                check_in_date__lte=cohort.check_out_date,
                check_out_date__gte=cohort.check_in_date,
            )
            .exclude(pk=cohort.pk)
            .values_list("rooms__pk", flat=True)
        )
        for room in Resource.objects.filter(
            resource_type="room", room_category="lodging"
        ).order_by("floor", "code"):
            available_rooms.append(
                {
                    "room": room,
                    "selected": room.pk in selected,
                    "blocked": room.pk in blocked or room.status != Resource.Status.ACTIVE,
                }
            )

    response = render(
        request,
        "lodging/workspace.html",
        {
            "cohorts": cohorts,
            "cohort_cards": cohort_cards,
            "public_pending_requests": public_pending_requests,
            "operations_summary": operations_summary,
            "can_manage_course_operations": can_manage_course_operations,
            "cohort": cohort,
            "cohort_booking_state": cohort_booking_state,
            "cohort_booking_message": cohort_booking_message,
            "rooms": rooms,
            "form": form,
            "available_rooms": available_rooms,
            "selected_assignment": selected_assignment,
            "assignment_open": assignment_open,
            "occupancy": occupancy,
            "room_filter": room_filter,
            "arrival": arrival,
            "arrival_filter": arrival_filter,
            "move_student": move_student,
            "move_form": move_form,
            "can_mark_no_show": bool(cohort and timezone.localdate() >= cohort.check_in_date),
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response

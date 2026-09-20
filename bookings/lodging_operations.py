"""Staff workspace presentation; allocation rules remain in lodging_services."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .lodging_models import CourseLodgingCohort
from .lodging_services import (
    assign_lodging_bed,
    can_access_lodging_management,
    can_manage_cohort,
    cohort_hold_range,
    request_general_lodging,
    update_cohort_allocation,
)
from .models import BookingResource
from .services import BookingConflict
from resources.models import Resource


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


class GeneralRequestForm(forms.Form):
    room = forms.ModelChoiceField(label="ห้องพัก", queryset=Resource.objects.none())
    check_in = forms.DateField(label="วันเข้าพัก (14:00 น.)", widget=forms.DateInput(attrs={"type": "date"}))
    check_out = forms.DateField(label="วันออก (12:00 น.)", widget=forms.DateInput(attrs={"type": "date"}))
    phone = forms.CharField(label="เบอร์โทรติดต่อ", max_length=30)
    note = forms.CharField(label="หมายเหตุ", required=False, max_length=1000,
                           widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["room"].queryset = Resource.objects.filter(resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.LODGING, status=Resource.Status.ACTIVE).order_by("code")


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


@login_required
def general_request(request):
    form = GeneralRequestForm(request.POST if request.method == "POST" else None,
                              initial={"phone": request.user.phone})
    if request.method == "POST" and form.is_valid():
        try:
            booking = request_general_lodging(actor=request.user, **form.cleaned_data)
        except (ValidationError, BookingConflict) as exc:
            form.add_error(None, " · ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
        else:
            messages.success(request, "ส่งคำขอแล้ว กรุณารอเจ้าหน้าที่อนุมัติก่อนเข้าพัก")
            return redirect("bookings:booking_detail", id=booking.pk)
    return render(request, "lodging/general_request.html", {"form": form})


@login_required
def lodging_workspace(request):
    if not can_access_lodging_management(request.user):
        raise PermissionDenied
    cohorts = CourseLodgingCohort.objects.all().order_by("-check_in_date")
    if not (request.user.is_superuser or request.user.has_perm("bookings.change_courselodgingcohort")):
        cohorts = cohorts.filter(supervisor=request.user)
    slug = request.GET.get("cohort")
    cohort = get_object_or_404(cohorts, slug=slug) if slug else cohorts.first()
    room_filter = _room_filter(request.GET.get("room_filter"))
    form, rooms, available_rooms, selected_assignment, assignment_open = None, [], [], None, False
    occupancy = {
        "capacity": 0,
        "assigned": 0,
        "free_beds": 0,
        "checked_in": 0,
        "rooms_total": 0,
        "rooms_free": 0,
        "rooms_full": 0,
    }
    if cohort:
        if not can_manage_cohort(request.user, cohort):
            raise PermissionDenied
        assignment_open = _assignment_is_open(cohort)
        allocating = request.method == "POST" and request.POST.get("action") == "allocation"
        if allocating:
            try:
                update_cohort_allocation(cohort=cohort,
                    rooms=Resource.objects.filter(pk__in=request.POST.getlist("rooms")),
                    check_in_date=cohort.check_in_date, check_out_date=cohort.check_out_date,
                    allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
                    is_active=request.POST.get("is_active") == "on", beds_per_room=cohort.beds_per_room,
                    actor=request.user)
            except (ValidationError, ValueError, IntegrityError) as exc:
                messages.error(request, " · ".join(exc.messages) if isinstance(exc, ValidationError) else "กรุณาตรวจห้องที่เลือกอีกครั้ง")
            else:
                messages.success(request, "บันทึกการจัดสรรห้องและสถานะรับจองแล้ว")
                return redirect(request.get_full_path())
        if request.method == "GET":
            selected_assignment = _assignment_selection(cohort, request.GET.get("room"), request.GET.get("bed"))
        initial = None
        if selected_assignment:
            initial = {
                "room_id": str(selected_assignment["room"].pk),
                "bed_number": str(selected_assignment["bed_number"]),
            }
        form = AssignmentForm(request.POST if request.method == "POST" and not allocating else None,
                              cohort=cohort, initial=initial)
        if request.method == "POST" and not allocating and form.is_valid():
            try:
                assign_lodging_bed(cohort=cohort, actor=request.user, **form.cleaned_data)
            except (ValidationError, IntegrityError) as exc:
                form.add_error(None, " · ".join(exc.messages) if isinstance(exc, ValidationError) else "เตียงถูกจองแล้ว กรุณาตรวจสอบอีกครั้ง")
            else:
                messages.success(request, "จัดผู้เข้าพักเรียบร้อยแล้ว")
                return redirect(request.get_full_path())
        students = list(cohort.students.select_related("room").order_by("bed_number"))
        all_rooms = []
        for room in cohort.rooms.order_by("floor", "code"):
            occupants = {s.bed_number: s for s in students if s.room_id == room.pk}
            free = cohort.beds_per_room - len(occupants)
            all_rooms.append({"room": room, "free": free,
                              "assignable": assignment_open and room.status == Resource.Status.ACTIVE,
                              "beds": [{"number": n, "student": occupants.get(n)} for n in range(1, cohort.beds_per_room + 1)]})
        occupancy = {
            "capacity": len(all_rooms) * cohort.beds_per_room,
            "assigned": len(students),
            "free_beds": max(0, len(all_rooms) * cohort.beds_per_room - len(students)),
            "checked_in": sum(1 for student in students if student.checked_in_at),
            "rooms_total": len(all_rooms),
            "rooms_free": sum(1 for item in all_rooms if item["free"] > 0),
            "rooms_full": sum(1 for item in all_rooms if item["free"] == 0),
        }
        if room_filter == "free":
            rooms = [item for item in all_rooms if item["free"] > 0]
        elif room_filter == "full":
            rooms = [item for item in all_rooms if item["free"] == 0]
        else:
            rooms = all_rooms
        selected = set(cohort.rooms.values_list("pk", flat=True))
        hold = cohort_hold_range(cohort.check_in_date, cohort.check_out_date)
        blocked = set(BookingResource.objects.filter(released_at__isnull=True, hold__overlap=hold).values_list("resource_id", flat=True))
        blocked.update(CourseLodgingCohort.objects.filter(allocation_status="allocated",
            check_in_date__lte=cohort.check_out_date, check_out_date__gte=cohort.check_in_date)
            .exclude(pk=cohort.pk).values_list("rooms__pk", flat=True))
        for room in Resource.objects.filter(resource_type="room", room_category="lodging").order_by("floor", "code"):
            available_rooms.append({"room": room, "selected": room.pk in selected,
                                    "blocked": room.pk in blocked or room.status != Resource.Status.ACTIVE})
    response = render(request, "lodging/workspace.html", {"cohorts": cohorts, "cohort": cohort,
                      "rooms": rooms, "form": form, "available_rooms": available_rooms,
                      "selected_assignment": selected_assignment, "assignment_open": assignment_open,
                      "occupancy": occupancy, "room_filter": room_filter})
    response["Cache-Control"] = "private, no-store"
    return response

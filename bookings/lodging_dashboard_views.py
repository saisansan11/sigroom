import csv
from datetime import date
from io import StringIO

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from audit.services import audit
from resources.models import Resource
from .lodging_billing import ZERO, save_meter, select_lodging_rate
from .lodging_dashboard import room_occupancy
from .lodging_models import LodgingMeterReading, LodgingRate
from .lodging_services import can_access_lodging_management, can_manage_cohort
from .services import can_view_details


class MeterForm(forms.Form):
    check_in_date = forms.DateField(
        label="วันเข้าพัก",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    check_out_date = forms.DateField(
        label="วันออก",
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    meter_in = forms.DecimalField(label="เลขมิเตอร์เข้า", max_digits=12, decimal_places=3, min_value=0)
    meter_out = forms.DecimalField(label="เลขมิเตอร์ออก (เว้นว่างจนกว่าจะออก)", max_digits=12, decimal_places=3, min_value=0, required=False)
    unit_price = forms.DecimalField(label="ราคาค่าไฟต่อหน่วย (ต้องระบุเอง)", max_digits=10, decimal_places=4, min_value=0, required=False)


def _staff(request):
    if not can_access_lodging_management(request.user):
        raise PermissionDenied("คุณไม่มีสิทธิ์เข้าดูแดชบอร์ดห้องพัก")


def _selection(request):
    try:
        day = date.fromisoformat(request.GET.get("day", "")) if request.GET.get("day") else timezone.localdate()
    except ValueError as exc:
        raise ValidationError("กรุณาเลือกวันที่ให้ถูกต้อง") from exc
    if not 2000 <= day.year <= 2199:
        raise ValidationError("เลือกวันที่ระหว่างปี 2543 ถึง 2742")
    floor = request.GET.get("floor", "all")
    status = request.GET.get("status", "all")
    return {"day": day, "floor": floor if floor in {"all", "4", "5"} else "all",
            "status": status if status in {"all", "empty", "occupied", "full"} else "all"}


def _filtered(rows, selection):
    return [row for row in rows if (selection["floor"] == "all" or row["room"].floor == selection["floor"])
            and (selection["status"] == "all" or row["status"] == selection["status"])]


def _private(response):
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@login_required
@require_GET
def dashboard(request):
    _staff(request)
    try:
        selection = _selection(request)
    except ValidationError as exc:
        return HttpResponse(" · ".join(exc.messages), status=400)
    rows = _filtered(room_occupancy(selection["day"]), selection)
    context = {**selection, "rows": rows, "summary": {
        "empty_rooms": sum(row["status"] == "empty" for row in rows),
        "free_beds": sum(row["free"] for row in rows), "people": sum(row["occupied"] for row in rows),
        "arrivals": sum(row["arrivals"] for row in rows), "departures": sum(row["departures"] for row in rows),
        "total": sum((row["total"] for row in rows), ZERO),
        "missing_rates": sum(row["missing_rates"] for row in rows),
        "estimated": any(row["estimated"] for row in rows),
    }}
    template = "lodging/partials/dashboard_grid.html" if request.headers.get("HX-Target") == "lodging-dashboard-grid" else "lodging/dashboard.html"
    return _private(render(request, template, context))


@login_required
@require_http_methods(["GET", "POST"])
def room_panel(request, room_id):
    _staff(request)
    room = get_object_or_404(Resource.objects.exclude(status="retired"), pk=room_id, resource_type="room", room_category="lodging")
    try:
        selection = _selection(request)
    except ValidationError as exc:
        return HttpResponse(" · ".join(exc.messages), status=400)
    form = None
    if request.method == "POST":
        if request.POST.get("action") == "rate":
            kind = request.POST.get("kind")
            source_id = request.POST.get("source_id")
            rate_id = request.POST.get("rate_id")
            if kind not in {"student", "booking"}:
                return HttpResponse("รายการที่ส่งไม่ถูกต้อง", status=400)
            try:
                select_lodging_rate(
                    actor=request.user,
                    kind=kind,
                    source_id=source_id,
                    rate_id=rate_id,
                    room=room,
                )
            except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
                messages.error(
                    request,
                    " · ".join(exc.messages) if isinstance(exc, ValidationError) and hasattr(exc, "messages") else "กรุณาเลือกอัตราที่ถูกต้อง",
                )
            else:
                messages.success(request, "บันทึกอัตราที่เลือกแล้ว")
        elif request.POST.get("action") == "meter":
            form = MeterForm(request.POST)
            if form.is_valid():
                try:
                    save_meter(actor=request.user, room_id=room.pk, **form.cleaned_data)
                except ValidationError as exc:
                    form.add_error(None, " · ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
                else:
                    messages.success(request, "บันทึกมิเตอร์แล้ว ค่าไฟคิดรวมทั้งห้อง")
                    form = None
        else:
            return HttpResponse("รายการที่ส่งไม่ถูกต้อง", status=400)
    row = next((row for row in room_occupancy(selection["day"]) if row["room"].pk == room.pk), None)
    if row is None:
        return HttpResponse("ห้องนี้ปลดระวางแล้ว", status=404)
    for occupant in row["occupants"]:
        permitted = can_manage_cohort(request.user, occupant["source"].cohort) if occupant["kind"] == "student" else can_view_details(request.user, occupant["source"])
        occupant["can_manage_rate"] = permitted
        if not permitted:
            occupant["name"] = "ผู้พักที่อยู่ในความดูแลของเจ้าหน้าที่อื่น"
            occupant["source"] = None
    if room.lodging_cooling == Resource.Cooling.AIR:
        reading = LodgingMeterReading.objects.filter(
            room=room, check_in_date__lte=selection["day"], check_out_date__gte=selection["day"]
        ).first()
        if not reading and row["stays"]:
            stay = row["stays"][0]
            reading = LodgingMeterReading.objects.filter(
                room=room, check_in_date=stay["check_in"], check_out_date=stay["check_out"]
            ).first()
        if reading:
            initial = {
                "check_in_date": reading.check_in_date,
                "check_out_date": reading.check_out_date,
                "meter_in": reading.meter_in,
                "meter_out": reading.meter_out,
                "unit_price": reading.unit_price,
            }
            form = form or MeterForm(initial=initial)
        elif row["stays"]:
            stay = row["stays"][0]
            initial = {
                "check_in_date": stay["check_in"],
                "check_out_date": stay["check_out"],
            }
            form = form or MeterForm(initial=initial)
    context = {**selection, "row": row, "meter_form": form,
        "is_partial": request.headers.get("HX-Target") == "lodging-room-panel",
        "rates": LodgingRate.objects.filter(cooling=room.lodging_cooling, effective_from__lte=selection["day"])}
    template = "lodging/partials/dashboard_room.html" if request.headers.get("HX-Target") == "lodging-room-panel" else "lodging/dashboard_room.html"
    return _private(render(request, template, context))


def _csv_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


@login_required
@require_GET
def export_csv(request):
    _staff(request)
    try:
        selection = _selection(request)
    except ValidationError as exc:
        return HttpResponse(" · ".join(exc.messages), status=400)
    rows = _filtered(room_occupancy(selection["day"]), selection)
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["วันที่", "ห้อง", "ชั้น", "ประเภท", "เตียง", "ผู้พัก", "ค่าที่พัก", "ค่าไฟรวมทั้งห้อง", "ยอดรวม", "สถานะยอด"])
    for row in rows:
        writer.writerow([_csv_cell(value) for value in [selection["day"].isoformat(), row["room"].code,
            row["room"].floor, row["room"].get_lodging_cooling_display() or "ยังไม่ระบุ", row["capacity"],
            row["occupied"], row["accommodation"], row["electricity"], row["total"],
            "ยังขาดอัตรา/ประมาณการ" if row["missing_rates"] else "ประมาณการ" if row["estimated"] else "คำนวณแล้ว"]])
    response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="lodging-room-totals.csv"'
    audit(request.user, "bookings.lodging_dashboard", selection["day"], "lodging_totals_csv_exported",
          after={"rooms": len(rows), "floor": selection["floor"], "status": selection["status"]})
    return _private(response)

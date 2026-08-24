import csv

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render

from accounts.models import Unit
from audit.services import audit

from .services import CSV_COLUMNS, REPORT_KEYS, accessible_rooms, build_report, build_reports, can_access_reports, parse_month


@login_required
def dashboard(request):
    if not can_access_reports(request.user):
        raise PermissionDenied
    error = ""
    try:
        start, end, month_value = parse_month(request.GET.get("month"))
    except ValueError as exc:
        error = str(exc)
        start, end, month_value = parse_month(None)
    room_code = request.GET.get("room", "").strip()
    unit_text = request.GET.get("unit", "").strip()
    unit_id = int(unit_text) if unit_text.isdigit() else None
    report_key = request.GET.get("report", "")
    if request.GET.get("format") == "csv":
        if report_key not in REPORT_KEYS:
            raise PermissionDenied("ไม่พบรายงานที่ขอส่งออก")
        report_rows = build_report(report_key, request.user, start, end, room_code, unit_id)
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="sigroom-{report_key}-{month_value}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        columns = CSV_COLUMNS[report_key]
        writer.writerow([label for key, label in columns])
        for row in report_rows:
            writer.writerow([row.get(key, "") for key, label in columns])
        audit(request.user, "reports.export", report_key, "report_csv_exported", after={"month": month_value, "room": room_code, "unit_id": unit_id})
        return response

    reports = build_reports(request.user, start, end, room_code, unit_id)
    return render(request, "reports/dashboard.html", {
        "reports": reports,
        "rooms": accessible_rooms(request.user),
        "units": Unit.objects.filter(is_active=True),
        "month_value": month_value,
        "selected_room": room_code,
        "selected_unit": unit_id,
        "error": error,
    })

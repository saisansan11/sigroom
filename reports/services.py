import calendar
from collections import defaultdict
from datetime import datetime, time

from django.db.models import Q
from django.utils import timezone

from accounts.models import Unit
from approvals.models import Approval
from approvals.services import sla_deadline
from bookings.models import Booking, Preemption
from resources.models import Resource, ResourceApprover


REPORT_KEYS = ("room_usage", "cancellation", "approval", "preemption", "equipment")


def can_access_reports(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(
        user.is_superuser
        or user.custodied_resources.filter(resource_type=Resource.Type.ROOM).exists()
        or ResourceApprover.objects.filter(user=user, resource__resource_type=Resource.Type.ROOM).exists()
    )


def accessible_rooms(user):
    queryset = Resource.objects.filter(resource_type=Resource.Type.ROOM).select_related("rule", "owner_unit")
    if user.is_superuser:
        return queryset
    return queryset.filter(Q(custodians=user) | Q(approvers__user=user)).distinct()


def parse_month(value, now=None):
    local_now = timezone.localtime(now or timezone.now())
    if not value:
        year, month = local_now.year, local_now.month
    else:
        try:
            year_text, month_text = value.split("-", 1)
            year, month = int(year_text), int(month_text)
            if year >= 2400:
                year -= 543
            if month < 1 or month > 12:
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError("เดือนต้องอยู่ในรูป ปปปป-ดด เช่น 2569-08")
    zone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime(year, month, 1), zone)
    if month == 12:
        end = timezone.make_aware(datetime(year + 1, 1, 1), zone)
    else:
        end = timezone.make_aware(datetime(year, month + 1, 1), zone)
    return start, end, f"{year + 543:04d}-{month:02d}"


def filtered_rooms(user, room_code=""):
    rooms = accessible_rooms(user)
    if room_code:
        rooms = rooms.filter(code=room_code)
    return rooms


def _hours(booking):
    return round((booking.end_at - booking.start_at).total_seconds() / 3600, 2)


def _percent(numerator, denominator):
    return round(numerator * 100 / denominator, 2) if denominator else 0


def _thai_datetime_text(value):
    local = timezone.localtime(value)
    return f"{local.day:02d}/{local.month:02d}/{local.year + 543} {local:%H:%M}"


def room_usage_report(user, start, end, room_code="", unit_id=None):
    rooms = list(filtered_rooms(user, room_code))
    room_ids = [room.pk for room in rooms]
    queryset = Booking.objects.filter(
        room_id__in=room_ids,
        start_at__gte=start,
        start_at__lt=end,
        request_status=Booking.RequestStatus.APPROVED,
    ).select_related("room", "unit")
    if unit_id:
        queryset = queryset.filter(unit_id=unit_id)
    grouped = defaultdict(lambda: {"approved_hours": 0.0, "used_hours": 0.0})
    for booking in queryset:
        key = (booking.room_id, booking.purpose, booking.unit_id)
        duration = _hours(booking)
        grouped[key]["approved_hours"] += duration
        if booking.usage_status == Booking.UsageStatus.USED:
            grouped[key]["used_hours"] += duration
    room_by_id = {room.pk: room for room in rooms}
    unit_by_id = {unit.pk: unit for unit in Unit.objects.filter(pk__in={key[2] for key in grouped})}
    purpose_labels = dict(Booking.Purpose.choices)
    days = calendar.monthrange(start.year, start.month)[1]
    rows = []
    for (room_id, purpose, row_unit_id), totals in sorted(grouped.items(), key=lambda item: (room_by_id[item[0][0]].code, item[0][1], item[0][2])):
        room = room_by_id[room_id]
        rule = getattr(room, "rule", None)
        service_hours = 0.0
        if rule:
            start_time = time.fromisoformat(rule.service_start) if isinstance(rule.service_start, str) else rule.service_start
            end_time = time.fromisoformat(rule.service_end) if isinstance(rule.service_end, str) else rule.service_end
            if end_time > start_time:
                service_hours = round((datetime.combine(start.date(), end_time) - datetime.combine(start.date(), start_time)).total_seconds() / 3600 * days, 2)
        rows.append({
            "room": room.code,
            "purpose": purpose_labels.get(purpose, purpose),
            "unit": unit_by_id[row_unit_id].code if row_unit_id in unit_by_id else "-",
            "used_hours": round(totals["used_hours"], 2),
            "approved_hours": round(totals["approved_hours"], 2),
            "service_hours": service_hours,
            "used_rate": _percent(totals["used_hours"], service_hours),
            "approved_rate": _percent(totals["approved_hours"], service_hours),
        })
    return rows


def cancellation_report(user, start, end, room_code="", unit_id=None):
    room_ids = filtered_rooms(user, room_code).values_list("pk", flat=True)
    queryset = Booking.objects.filter(room_id__in=room_ids, start_at__gte=start, start_at__lt=end).exclude(request_status=Booking.RequestStatus.DRAFT).select_related("unit", "requester")
    if unit_id:
        queryset = queryset.filter(unit_id=unit_id)
    grouped = defaultdict(lambda: {"total": 0, "cancelled": 0, "no_show": 0, "unit": "", "person": ""})
    for booking in queryset:
        key = (booking.unit_id, booking.requester_id)
        row = grouped[key]
        row["unit"] = booking.unit.code
        row["person"] = booking.requester.display_name
        row["total"] += 1
        row["cancelled"] += booking.request_status == Booking.RequestStatus.CANCELLED
        row["no_show"] += booking.usage_status == Booking.UsageStatus.NO_SHOW
    rows = []
    for row in grouped.values():
        exceptional = row["cancelled"] + row["no_show"]
        rows.append({**row, "cancelled_rate": _percent(row["cancelled"], row["total"]), "no_show_rate": _percent(row["no_show"], row["total"]), "combined_rate": _percent(exceptional, row["total"])})
    return sorted(rows, key=lambda row: (row["unit"], row["person"]))


def approval_report(user, start, end, room_code="", unit_id=None):
    room_ids = filtered_rooms(user, room_code).values_list("pk", flat=True)
    queryset = Approval.objects.filter(
        booking__room_id__in=room_ids,
        acted_at__gte=start,
        acted_at__lt=end,
        action__in=[Approval.Action.APPROVED, Approval.Action.REJECTED, Approval.Action.EXPIRED],
    ).select_related("acted_by", "booking", "amendment")
    if unit_id:
        queryset = queryset.filter(booking__unit_id=unit_id)
    grouped = defaultdict(lambda: {"decisions": 0, "total_seconds": 0.0, "over_sla": 0, "expired": 0, "approver": ""})
    for approval in queryset:
        key = approval.acted_by_id or 0
        row = grouped[key]
        row["approver"] = approval.acted_by.display_name if approval.acted_by else "ระบบ"
        item = approval.amendment or approval.booking
        submitted_at = item.submitted_at or approval.booking.created_at
        if approval.action in {Approval.Action.APPROVED, Approval.Action.REJECTED}:
            row["decisions"] += 1
            row["total_seconds"] += max(0, (approval.acted_at - submitted_at).total_seconds())
            row["over_sla"] += approval.acted_at > sla_deadline(item)
        if approval.action == Approval.Action.EXPIRED:
            row["expired"] += 1
    rows = []
    for row in grouped.values():
        average_hours = row.pop("total_seconds") / 3600 / row["decisions"] if row["decisions"] else 0
        rows.append({**row, "average_hours": round(average_hours, 2)})
    return sorted(rows, key=lambda row: row["approver"])


def preemption_report(user, start, end, room_code="", unit_id=None):
    room_ids = filtered_rooms(user, room_code).values_list("pk", flat=True)
    queryset = Preemption.objects.filter(displaced__room_id__in=room_ids, created_at__gte=start, created_at__lt=end).select_related("displaced__room", "displaced__unit", "ordered_by")
    if unit_id:
        queryset = queryset.filter(displaced__unit_id=unit_id)
    rows = []
    for item in queryset:
        acknowledged = "ถือว่ารับทราบ" if item.deemed_acknowledged else ("รับทราบแล้ว" if item.acknowledged_at else "รอรับทราบ")
        rows.append({
            "at": _thai_datetime_text(item.created_at),
            "room": item.displaced.room.code,
            "booking": str(item.displaced_id).replace("-", "")[:8].upper(),
            "reference_no": item.reference_no,
            "ordered_by": item.ordered_by.display_name,
            "acknowledged": acknowledged,
        })
    return rows


def equipment_report(user, start, end, room_code="", unit_id=None):
    room_ids = filtered_rooms(user, room_code).values_list("pk", flat=True)
    queryset = Booking.objects.filter(
        room_id__in=room_ids,
        start_at__gte=start,
        start_at__lt=end,
        request_status=Booking.RequestStatus.APPROVED,
        usage_status=Booking.UsageStatus.USED,
        equipment__isnull=False,
    ).select_related("unit").prefetch_related("equipment")
    if unit_id:
        queryset = queryset.filter(unit_id=unit_id)
    grouped = defaultdict(lambda: {"uses": 0, "hours": 0.0, "equipment": ""})
    for booking in queryset.distinct():
        for equipment in booking.equipment.all():
            row = grouped[equipment.pk]
            row["equipment"] = f"{equipment.code} {equipment.name}"
            row["uses"] += 1
            row["hours"] += _hours(booking)
    return sorted(({**row, "hours": round(row["hours"], 2)} for row in grouped.values()), key=lambda row: row["equipment"])


def build_reports(user, start, end, room_code="", unit_id=None):
    return {
        "room_usage": room_usage_report(user, start, end, room_code, unit_id),
        "cancellation": cancellation_report(user, start, end, room_code, unit_id),
        "approval": approval_report(user, start, end, room_code, unit_id),
        "preemption": preemption_report(user, start, end, room_code, unit_id),
        "equipment": equipment_report(user, start, end, room_code, unit_id),
    }


REPORT_BUILDERS = {
    "room_usage": room_usage_report,
    "cancellation": cancellation_report,
    "approval": approval_report,
    "preemption": preemption_report,
    "equipment": equipment_report,
}


def build_report(report_key, user, start, end, room_code="", unit_id=None):
    try:
        builder = REPORT_BUILDERS[report_key]
    except KeyError as exc:
        raise ValueError("ไม่พบรายงานที่ขอ") from exc
    return builder(user, start, end, room_code, unit_id)


CSV_COLUMNS = {
    "room_usage": [("room", "ห้อง"), ("purpose", "ประเภท"), ("unit", "หน่วย"), ("used_hours", "ชั่วโมงใช้จริง"), ("approved_hours", "ชั่วโมงจองอนุมัติ"), ("service_hours", "ชั่วโมงให้บริการ"), ("used_rate", "อัตราใช้จริง (%)"), ("approved_rate", "อัตราจองอนุมัติ (%)")],
    "cancellation": [("unit", "หน่วย"), ("person", "บุคคล"), ("total", "การจองทั้งหมด"), ("cancelled", "ยกเลิก"), ("cancelled_rate", "อัตรายกเลิก (%)"), ("no_show", "ไม่มาใช้"), ("no_show_rate", "อัตราไม่มาใช้ (%)"), ("combined_rate", "อัตรารวม (%)")],
    "approval": [("approver", "ผู้อนุมัติ"), ("decisions", "จำนวนตัดสิน"), ("average_hours", "เวลาเฉลี่ย (ชม.)"), ("over_sla", "เกิน SLA"), ("expired", "หมดอายุ")],
    "preemption": [("at", "วันเวลา"), ("room", "ห้อง"), ("booking", "รหัสการจอง"), ("reference_no", "เลขอ้างอิง"), ("ordered_by", "ผู้สั่ง"), ("acknowledged", "สถานะรับทราบ")],
    "equipment": [("equipment", "อุปกรณ์ส่วนกลาง"), ("uses", "จำนวนครั้งที่ใช้"), ("hours", "ชั่วโมงที่ใช้")],
}

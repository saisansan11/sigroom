"""
กฎธุรกิจของการจอง — view/template ห้ามมีตรรกะเหล่านี้เอง

M0/M1 ครอบคลุม: คำนวณช่วงถือครองรวม buffer (FR-07) และสร้าง/ส่งการจองพร้อมถือครอง
ทรัพยากรภายใต้ exclusion constraint (FR-09) โดยแปลงข้อผิดพลาดของฐานข้อมูลเป็นข้อความไทย
"""
from dataclasses import dataclass
from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.db.models import QuerySet
from django.utils import timezone

from resources.models import Resource, ResourceRule
from audit.services import audit

from .models import Booking, BookingResource


class BookingConflict(Exception):
    """ทรัพยากรไม่ว่างในช่วงเวลาที่ขอ"""

    def __init__(self, resource: Resource):
        self.resource = resource
        super().__init__(f"{resource.code} {resource.name} ไม่ว่างในช่วงเวลาที่เลือก")


@dataclass(frozen=True)
class RoomSearchResult:
    """ผลค้นหาห้องหนึ่งรายการ ใช้ได้ทั้งใน view และเทสโดยไม่ย้ายกฎไป template"""

    room: Resource
    reason: str = ""
    capacity_warning: bool = False

    @property
    def approval_label(self) -> str:
        rule = getattr(self.room, "rule", None)
        if rule and rule.approval_policy == ResourceRule.ApprovalPolicy.REQUIRED:
            return "ต้องอนุมัติ"
        return "อนุมัติอัตโนมัติ"


def compute_hold(resource: Resource, start_at: datetime, end_at: datetime) -> DateTimeTZRange:
    """ช่วงถือครอง = [start - buffer_before, end + buffer_after) ตาม FR-07"""
    rule = getattr(resource, "rule", None)
    before = timedelta(minutes=rule.buffer_before_min if rule else 0)
    after = timedelta(minutes=rule.buffer_after_min if rule else 0)
    return DateTimeTZRange(start_at - before, end_at + after, "[)")


def _resources_for(booking: Booking, equipment: list[Resource]) -> list[Resource]:
    return [booking.room, *equipment]


@transaction.atomic
def place_holds(booking: Booking, equipment: list[Resource] | None = None) -> list[BookingResource]:
    """
    สร้างแถวถือครองให้ห้อง + อุปกรณ์ส่วนกลางของการจอง
    ถ้าชน ฐานข้อมูลจะโยน IntegrityError จาก excl_overlapping_holds → แปลงเป็น BookingConflict
    ใช้ savepoint ต่อทรัพยากร เพื่อบอกได้ว่าชนที่ไหน (FR-06)
    """
    holds: list[BookingResource] = []
    for resource in _resources_for(booking, equipment or []):
        hold = compute_hold(resource, booking.start_at, booking.end_at)
        try:
            with transaction.atomic():
                holds.append(BookingResource.objects.create(booking=booking, resource=resource, hold=hold))
        except IntegrityError as exc:
            if "excl_overlapping_holds" in str(exc):
                raise BookingConflict(resource) from exc
            raise
    return holds


@transaction.atomic
def release_holds(booking: Booking) -> int:
    """ปลดช่วงถือครองทั้งหมดของการจอง (ใช้เมื่อ ปฏิเสธ/ยกเลิก/หมดอายุ/ถูกย้าย — FR-10)"""
    return booking.holds.filter(released_at__isnull=True).update(released_at=timezone.now())


def approval_policy_for_values(room: Resource, has_external_attendees: bool) -> str:
    """แกนประเมินนโยบายที่ใช้ร่วมกันระหว่างการจองปกติและ amendment"""
    rule = getattr(room, "rule", None)
    if rule and rule.approval_policy == ResourceRule.ApprovalPolicy.REQUIRED:
        return ResourceRule.ApprovalPolicy.REQUIRED
    if has_external_attendees:
        return ResourceRule.ApprovalPolicy.REQUIRED
    return ResourceRule.ApprovalPolicy.AUTO


def approval_policy_for(booking: Booking) -> str:
    """
    ประเมินนโยบายอนุมัติจากห้องและข้อมูลคำขอ (D1, SRS 12.2)
    - ห้องนโยบาย "ต้องอนุมัติ" → ต้องอนุมัติ
    - มีผู้เข้าร่วมจากภายนอก → ต้องอนุมัติ แม้ห้องเป็นอัตโนมัติ
    """
    return approval_policy_for_values(booking.room, booking.has_external_attendees)


def validate_booking_window(
    resource: Resource,
    start: datetime,
    end: datetime,
    user,
    now: datetime | None = None,
) -> list[str]:
    """ตรวจช่วงเวลาและสิทธิ์ตามกฎรายห้อง คืนข้อความไทยทั้งหมดที่พบ"""
    errors: list[str] = []
    now = now or timezone.now()
    rule = getattr(resource, "rule", None)

    if resource.resource_type != Resource.Type.ROOM:
        errors.append("ทรัพยากรที่เลือกไม่ใช่ห้อง")
    if resource.status != Resource.Status.ACTIVE:
        errors.append("ห้องนี้งดให้บริการ")
    if end <= start:
        return [*errors, "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม"]
    if start < now:
        errors.append("เวลาเริ่มต้องไม่อยู่ในอดีต")
    if any(value.second or value.microsecond or value.minute % 15 for value in (start, end)):
        errors.append("เวลาเริ่มและสิ้นสุดต้องตรงช่วงละ 15 นาที")

    if not rule:
        return errors

    duration_min = int((end - start).total_seconds() // 60)
    if duration_min < rule.min_duration_min:
        errors.append(f"ต้องจองอย่างน้อย {rule.min_duration_min} นาที")
    if duration_min > rule.max_duration_min:
        errors.append(f"จองต่อครั้งได้ไม่เกิน {rule.max_duration_min} นาที")
    if start > now + timedelta(days=rule.max_advance_days):
        errors.append(f"จองล่วงหน้าได้ไม่เกิน {rule.max_advance_days} วัน")

    local_start = timezone.localtime(start)
    local_end = timezone.localtime(end)
    service_start = time.fromisoformat(rule.service_start) if isinstance(rule.service_start, str) else rule.service_start
    service_end = time.fromisoformat(rule.service_end) if isinstance(rule.service_end, str) else rule.service_end
    if local_start.date() != local_end.date() or local_start.time() < service_start or local_end.time() > service_end:
        errors.append(
            f"ห้องนี้ให้บริการ {service_start.strftime('%H:%M')}–{service_end.strftime('%H:%M')}"
        )

    if not getattr(user, "is_superuser", False) and rule.allowed_units.exists():
        user_unit_id = getattr(user, "unit_id", None)
        if not user_unit_id or not rule.allowed_units.filter(pk=user_unit_id).exists():
            errors.append("หน่วยงานของคุณไม่มีสิทธิ์จองห้องนี้")

    from resources.services import active_blackouts, active_outages

    blackouts = active_blackouts(resource, start, end)
    if blackouts:
        errors.append(f"ติดวันหยุด/กิจกรรมส่วนกลาง: {blackouts[0].title}")
    outages = active_outages(resource, start, end)
    if outages:
        errors.append(f"ห้องงดใช้: {outages[0].reason}")
    return errors


def _active_holds_overlapping(resource: Resource, hold: DateTimeTZRange) -> QuerySet[BookingResource]:
    return BookingResource.objects.filter(resource=resource, released_at__isnull=True, hold__overlap=hold)


def find_available_rooms(
    start: datetime,
    end: datetime,
    user,
    attendees: int | None = None,
    equipment_codes=(),
) -> tuple[list[RoomSearchResult], list[RoomSearchResult]]:
    """ค้นหาห้องพร้อมใช้และรายการที่ใช้ไม่ได้ โดยคำนวณ buffer และอุปกรณ์ร่วมด้วย"""
    available: list[RoomSearchResult] = []
    unavailable: list[RoomSearchResult] = []
    equipment = list(
        Resource.objects.filter(
            resource_type=Resource.Type.EQUIPMENT,
            status=Resource.Status.ACTIVE,
            code__in=list(equipment_codes),
        ).select_related("rule")
    )
    unavailable_equipment = [
        item for item in equipment if _active_holds_overlapping(item, compute_hold(item, start, end)).exists()
    ]

    rooms = Resource.objects.filter(resource_type=Resource.Type.ROOM).select_related("rule", "owner_unit")
    for room in rooms:
        errors = validate_booking_window(room, start, end, user)
        if not errors and _active_holds_overlapping(room, compute_hold(room, start, end)).exists():
            errors.append("ไม่ว่างในช่วงเวลาที่เลือก (รวมเวลาเตรียม/เก็บห้อง)")
        if not errors and unavailable_equipment:
            names = ", ".join(item.name for item in unavailable_equipment)
            errors.append(f"อุปกรณ์ส่วนกลางไม่ว่าง: {names}")
        result = RoomSearchResult(
            room=room,
            reason=" · ".join(errors),
            capacity_warning=bool(attendees and room.capacity and attendees > room.capacity),
        )
        (unavailable if errors else available).append(result)
    return available, unavailable


def _contact_for_room(room: Resource) -> str:
    custodian = room.custodians.exclude(phone="").first() or room.custodians.first()
    if not custodian:
        return "เจ้าหน้าที่ดูแลห้อง"
    phone = f" โทร {custodian.phone}" if custodian.phone else ""
    return f"{custodian.display_name}{phone}"


@transaction.atomic
def cancel_booking(booking: Booking, user, now: datetime | None = None) -> Booking:
    """ยกเลิกคำขอของตนเองก่อนเส้นตายและปลด hold ใน transaction เดียว"""
    now = now or timezone.now()
    if booking.requester_id != getattr(user, "pk", None) and not getattr(user, "is_superuser", False):
        raise PermissionError("คุณไม่มีสิทธิ์ยกเลิกการจองนี้")
    if booking.request_status in {
        Booking.RequestStatus.CANCELLED,
        Booking.RequestStatus.REJECTED,
        Booking.RequestStatus.EXPIRED,
    }:
        raise ValueError("การจองนี้ยกเลิกหรือสิ้นสุดแล้ว")
    rule = getattr(booking.room, "rule", None)
    cutoff = timedelta(hours=rule.cancel_cutoff_hours if rule else 4)
    if booking.start_at - now < cutoff:
        raise PermissionError(
            "พ้นเวลาแก้ไข/ยกเลิกด้วยตนเอง กรุณาติดต่อเจ้าหน้าที่ดูแลห้อง: "
            + _contact_for_room(booking.room)
        )
    before_status = booking.request_status
    booking.request_status = Booking.RequestStatus.CANCELLED
    booking.revision += 1
    booking.save(update_fields=["request_status", "revision", "updated_at"])
    pending_amendment = booking.amendments.filter(status="pending").first()
    if pending_amendment:
        from .amendment_services import withdraw_amendment

        withdraw_amendment(
            pending_amendment,
            user,
            "ถอนอัตโนมัติ: การจองถูกยกเลิก",
            now,
        )
    release_holds(booking)
    audit(user, "bookings.booking", booking.pk, "booking_cancelled", before={"request_status": before_status}, after={"request_status": booking.request_status})
    return booking


def _is_room_staff(user, room: Resource) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return room.custodians.filter(pk=user.pk).exists() or room.approvers.filter(user=user).exists()


def can_view_details(user, booking: Booking) -> bool:
    """คืน True เฉพาะผู้ที่ดูชื่อกิจกรรมและรายละเอียดเต็มได้"""
    if not getattr(user, "is_authenticated", False):
        return False
    if booking.preemption_as_incoming.filter(displaced__requester_id=user.pk).exists():
        return False
    if user.is_superuser or user.is_infosec_officer or booking.requester_id == user.pk:
        return True
    if booking.visibility == Booking.Visibility.SENSITIVE:
        return False
    if booking.unit_id and booking.unit_id == getattr(user, "unit_id", None):
        return True
    return _is_room_staff(user, booking.room)


def calendar_label(user, booking: Booking) -> str:
    if can_view_details(user, booking):
        return f"{booking.title} — {booking.room.code}"
    if booking.visibility == Booking.Visibility.NORMAL:
        return f"ไม่ว่าง — {booking.unit.name}"
    return "ไม่ว่าง"


FREQUENT_FIELDS = {
    "title",
    "responsible_name",
    "responsible_phone",
    "attendee_level",
    "layout",
}


def frequent_values(unit, field: str) -> list[str]:
    """รวมค่าอ้างอิงที่เปิดใช้ทั้งหมด (datalist กรองเองตอนพิมพ์) ตามด้วย 10 ค่าล่าสุดของหน่วย โดยไม่ซ้ำ"""
    if field not in FREQUENT_FIELDS:
        return []
    from .models import ReferenceValue

    result = list(dict.fromkeys(
        ReferenceValue.objects.filter(field=field, is_active=True).order_by("order", "value").values_list("value", flat=True)
    ))
    if not unit:
        return result
    values = Booking.objects.filter(unit=unit).exclude(**{field: ""}).order_by("-updated_at").values_list(field, flat=True)
    history_count = 0
    for value in values.iterator():
        if value not in result:
            result.append(value)
            history_count += 1
        if history_count == 10:
            break
    return result


POST_SUBMIT_EDITABLE_FIELDS = {
    "title",
    "responsible_name",
    "responsible_phone",
    "attendees",
    "attendee_level",
    "layout",
    "fixed_equipment_needed",
    "note",
}


def self_service_message(booking: Booking, now: datetime | None = None) -> str:
    """ข้อความเมื่อพ้นเส้นตายแก้ไข/ยกเลิก; ค่าว่างหมายถึงยังดำเนินการเองได้"""
    if booking.request_status == Booking.RequestStatus.DRAFT:
        return ""
    rule = getattr(booking.room, "rule", None)
    cutoff = timedelta(hours=rule.cancel_cutoff_hours if rule else 4)
    if booking.start_at - (now or timezone.now()) < cutoff:
        return (
            "พ้นเวลาแก้ไข/ยกเลิกด้วยตนเอง กรุณาติดต่อเจ้าหน้าที่ดูแลห้อง: "
            + _contact_for_room(booking.room)
        )
    return ""


def editable_fields(booking: Booking, now: datetime | None = None) -> set[str]:
    if self_service_message(booking, now):
        return set()
    if booking.request_status == Booking.RequestStatus.DRAFT:
        return {
            "date", "start_time", "end_time", "title", "purpose", "unit", "responsible_name",
            "responsible_phone", "attendees", "attendee_level", "layout", "fixed_equipment_needed",
            "fixed_equipment_choices", "fixed_equipment_extra", "equipment", "has_external_attendees",
            "external_attendees_note", "visibility", "note",
        }
    if booking.request_status in Booking.HOLDING_STATUSES:
        return set(POST_SUBMIT_EDITABLE_FIELDS)
    return set()


def _urgent_deadline(now: datetime) -> datetime:
    """สองวันทำการ (ข้ามวันหยุดส่วนกลาง) + 24 ชม. สำหรับจัดธงเร่งด่วน"""
    from approvals.services import is_business_day

    cursor = now
    business_days = 0
    while business_days < 2:
        cursor += timedelta(days=1)
        if is_business_day(timezone.localtime(cursor).date()):
            business_days += 1
    return cursor + timedelta(hours=24)


@transaction.atomic
def submit_booking(booking: Booking, equipment: list[Resource] | None = None) -> Booking:
    """
    ส่งคำขอ: ถือครองทรัพยากร แล้วตั้งสถานะตามนโยบาย (อัตโนมัติ → อนุมัติ, ต้องอนุมัติ → รออนุมัติ)
    การทำงานทั้งหมดอยู่ใน transaction เดียว — ถ้าชนจะไม่มีอะไรถูกบันทึก
    """
    if booking.request_status != Booking.RequestStatus.DRAFT:
        raise ValueError("ส่งได้เฉพาะคำขอสถานะร่าง")
    errors = validate_booking_window(booking.room, booking.start_at, booking.end_at, booking.requester)
    if errors:
        raise ValidationError(errors)
    now = timezone.now()
    booking.submitted_at = now
    policy = approval_policy_for(booking)
    booking.is_urgent = policy == ResourceRule.ApprovalPolicy.REQUIRED and booking.start_at < _urgent_deadline(now)
    booking.request_status = (
        Booking.RequestStatus.APPROVED if policy == ResourceRule.ApprovalPolicy.AUTO else Booking.RequestStatus.PENDING
    )
    booking.save()
    selected_equipment = list(equipment) if equipment is not None else list(booking.equipment.all())
    place_holds(booking, selected_equipment)
    audit(booking.requester, "bookings.booking", booking.pk, "booking_submitted", before={"request_status": Booking.RequestStatus.DRAFT}, after={"request_status": booking.request_status})
    return booking

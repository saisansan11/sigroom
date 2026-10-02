"""
กฎธุรกิจของการจอง — view/template ห้ามมีตรรกะเหล่านี้เอง

M0/M1 ครอบคลุม: คำนวณช่วงถือครองรวม buffer (FR-07) และสร้าง/ส่งการจองพร้อมถือครอง
ทรัพยากรภายใต้ exclusion constraint (FR-09) โดยแปลงข้อผิดพลาดของฐานข้อมูลเป็นข้อความไทย
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

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
    # ใช้ไม่ได้ "เพราะชนเวลาเท่านั้น" (ห้อง/อุปกรณ์ถูกถือครอง) — กฎอื่นผ่านหมด จึงเลื่อนเวลาแล้วอาจใช้ได้
    time_conflict_only: bool = False

    @property
    def approval_label(self) -> str:
        rule = getattr(self.room, "rule", None)
        if rule and rule.approval_policy == ResourceRule.ApprovalPolicy.REQUIRED:
            return "ต้องอนุมัติ"
        return "อนุมัติอัตโนมัติ"


@dataclass(frozen=True)
class NowAvailability:
    """ผลค้นหาห้องว่างช่วงถัดไปจากหน้าแรก (งาน A)."""

    start_at: datetime
    end_at: datetime
    groups: tuple[dict, ...]


NOW_ROOM_GROUPS = (
    {
        "key": "teaching",
        "label": "ห้องเรียน / ห้องปฏิบัติ",
        "categories": (Resource.Category.CLASSROOM, Resource.Category.LAB),
    },
    {
        "key": "meeting",
        "label": "ห้องประชุม",
        "categories": (Resource.Category.MEETING, Resource.Category.SPECIAL),
    },
    {
        "key": "online",
        "label": "ห้องสอนออนไลน์",
        "categories": (Resource.Category.ONLINE,),
    },
)


DEFAULT_TIME_PRESETS = (
    ("08:00", "12:00", "เช้า"),
    ("13:00", "16:00", "บ่าย"),
    # ห้องส่วนใหญ่เปิด 07:30–17:00 จึงจบ 16:30 เหลือเวลาเก็บห้องก่อนปิด
    ("08:00", "16:30", "ทั้งวัน"),
)


def time_presets() -> list[dict]:
    """ปุ่มช่วงเวลาสำเร็จรูป (งาน C) — อ่านจาก ReferenceValue field=time_preset, ว่างเมื่อไม่มีใช้ค่า default"""
    from .models import ReferenceValue, parse_time_preset

    presets = []
    rows = ReferenceValue.objects.filter(field="time_preset", is_active=True)
    for row in rows:
        parsed = parse_time_preset(row.value)
        if parsed:  # แถวผิดรูปแบบ (ข้อมูลเก่าก่อนมี clean) ข้ามไป ไม่ให้ฟอร์มพัง
            presets.append({"start": parsed[0], "end": parsed[1], "label": parsed[2]})
    if not presets:
        presets = [{"start": s, "end": e, "label": lb} for s, e, lb in DEFAULT_TIME_PRESETS]
    return presets


def rebook_default_date(original_date, today=None):
    """วันที่ default ของปุ่ม "จองแบบเดิมอีกครั้ง" (งาน C)

    ต้องห่างจากวันเดิมอย่างน้อย 7 วันเสมอ: candidate = วันเดิม + 7 แล้ววน +7 ขณะ candidate <= วันนี้
    (จองสัปดาห์ล่าสุด → +7 พอดี · จองเก่าเดือนก่อน → วันเดียวกันของสัปดาห์หน้า ·
    จองต้นฉบับวันพรุ่งนี้ → พรุ่งนี้ของสัปดาห์ถัดไป ไม่ใช่วันพรุ่งนี้ซ้ำ)
    """
    today = today or timezone.localdate()
    candidate = original_date + timedelta(days=7)
    while candidate <= today:
        candidate += timedelta(days=7)
    return candidate


def next_quarter_start(now: datetime | None = None) -> datetime:
    """คืนเวลาเริ่มที่เป็นช่วง 15 นาทีถัดไปแบบเวลาท้องถิ่น (งาน A)."""
    local_now = timezone.localtime(now or timezone.now())
    base = local_now.replace(second=0, microsecond=0)
    minutes = 15 - (base.minute % 15)
    return base + timedelta(minutes=minutes)


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
    resources = _resources_for(booking, equipment or [])
    resource_ids = {resource.pk for resource in resources}
    locked_resources = list(
        Resource.objects.select_for_update().filter(pk__in=resource_ids).order_by("pk")
    )
    locked_by_id = {resource.pk: resource for resource in locked_resources}
    if len(locked_by_id) != len(resource_ids):
        raise ValidationError("ทรัพยากรที่เลือกไม่พบในระบบ")

    holds: list[BookingResource] = []
    for resource in resources:
        resource = locked_by_id[resource.pk]
        from .lodging_services import cohort_conflict_for_resource

        if cohort_conflict_for_resource(resource, booking.start_at, booking.end_at):
            raise BookingConflict(resource)
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
    if room.room_category == Resource.Category.LODGING:
        return ResourceRule.ApprovalPolicy.REQUIRED
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
    if resource.room_category == Resource.Category.ONLINE:
        from .online_teaching import can_book_online_teaching

        if not can_book_online_teaching(user):
            errors.append("เฉพาะครูที่ได้รับสิทธิ์จองห้องสอนออนไลน์")
    if end <= start:
        return [*errors, "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม"]
    if start < now:
        errors.append("เวลาเริ่มต้องไม่อยู่ในอดีต")
    if any(value.second or value.microsecond or value.minute % 15 for value in (start, end)):
        errors.append("เวลาเริ่มและสิ้นสุดต้องตรงช่วงละ 15 นาที")

    from .lodging_services import cohort_conflict_for_resource

    if cohort_conflict_for_resource(resource, start, end):
        errors.append("ห้องพักถูกสงวนไว้สำหรับรอบหลักสูตรในช่วงวันที่เลือก")

    if not rule:
        return errors

    duration_min = int((end - start).total_seconds() // 60)
    # ห้องพักคิดเป็นช่วงเข้าพักข้ามวัน จึงไม่ใช้เพดานนาทีของห้องประชุม
    # แต่ยังตรวจวันล่วงหน้า การชน การงดใช้ และการสงวนหลักสูตรตามปกติ
    if resource.room_category != Resource.Category.LODGING:
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
    if resource.room_category != Resource.Category.LODGING and (local_start.date() != local_end.date() or local_start.time() < service_start or local_end.time() > service_end):
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
    room_categories=None,
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

    rooms = Resource.objects.filter(resource_type=Resource.Type.ROOM).select_related("rule", "owner_unit").prefetch_related("photos")
    if room_categories:
        rooms = rooms.filter(room_category__in=tuple(room_categories))
    for room in rooms:
        rule_errors = validate_booking_window(room, start, end, user)
        errors = list(rule_errors)
        if not errors and _active_holds_overlapping(room, compute_hold(room, start, end)).exists():
            errors.append("ไม่ว่างในช่วงเวลาที่เลือก (รวมเวลาเตรียม/เก็บห้อง)")
        if not errors and unavailable_equipment:
            names = ", ".join(item.name for item in unavailable_equipment)
            errors.append(f"อุปกรณ์ส่วนกลางไม่ว่าง: {names}")
        result = RoomSearchResult(
            room=room,
            reason=" · ".join(errors),
            capacity_warning=bool(attendees and room.capacity and attendees > room.capacity),
            time_conflict_only=bool(errors) and not rule_errors,
        )
        (unavailable if errors else available).append(result)
    # ห้องโปรดขึ้นก่อนเสมอ (งาน C) — stable sort คงลำดับเดิมภายในแต่ละกลุ่ม
    favorite_ids = (
        set(user.favorite_resources.values_list("pk", flat=True))
        if getattr(user, "is_authenticated", False)
        else set()
    )
    if favorite_ids:
        available.sort(key=lambda item: item.room.pk not in favorite_ids)
    return available, unavailable


def find_available_now(
    user,
    now: datetime | None = None,
    duration_minutes: int = 60,
    limit_per_group: int = 4,
) -> NowAvailability:
    """ค้นหาห้องว่างช่วง 60 นาทีถัดไปสำหรับการ์ดหน้าแรก.

    ใช้ validate_booking_window()/find_available_rooms() ชุดเดียวกับหน้าค้นหา
    จึงครอบคลุมชน, blackout, outage, เวลาเปิดบริการ, buffer และ allowed_units.
    """
    if duration_minutes <= 0:
        raise ValueError("duration_minutes ต้องมากกว่า 0")
    if limit_per_group <= 0:
        raise ValueError("limit_per_group ต้องมากกว่า 0")

    start = next_quarter_start(now)
    end = start + timedelta(minutes=duration_minutes)
    groups = []
    for group in NOW_ROOM_GROUPS:
        available, _ = find_available_rooms(
            start,
            end,
            user,
            room_categories=group["categories"],
        )
        groups.append(
            {
                "key": group["key"],
                "label": group["label"],
                "rooms": tuple(available[:limit_per_group]),
            }
        )
    return NowAvailability(start_at=start, end_at=end, groups=tuple(groups))


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


def can_view_online_link(user, booking: Booking) -> bool:
    """สิทธิ์เห็นลิงก์ห้องเรียนออนไลน์ — เข้มกว่า can_view_details() (งาน B)

    อนุญาตเฉพาะ ผู้จอง / superuser / จนท.ความมั่นคงสารสนเทศ / เจ้าหน้าที่ดูแลห้องและผู้อนุมัติของห้องนั้น
    คนหน่วยเดียวกันดูรายละเอียดอื่นได้ตาม can_view_details() แต่ต้องไม่เห็นลิงก์
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if booking.requester_id == user.pk:
        return True
    if user.is_superuser or user.is_infosec_officer:
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
    values = (
        Booking.objects.filter(unit=unit)
        .exclude(**{field: ""})
        .order_by("-updated_at", "-start_at", "-created_at")
        .values_list(field, flat=True)
    )
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
    "online_meeting_url",  # ครูมักได้ลิงก์ประชุมทีหลัง จึงต้องเติม/แก้ได้หลังส่งคำขอ (งาน B)
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


def remember_requester_phone(booking: Booking) -> None:
    """จำเบอร์จากฟอร์มกลับเข้าโปรไฟล์ เฉพาะกรณีโปรไฟล์เดิมยังว่าง."""
    requester = booking.requester
    phone = (booking.responsible_phone or "").strip()
    if not phone or getattr(requester, "phone", ""):
        return
    requester.phone = phone
    requester.save(update_fields=["phone"])


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
    remember_requester_phone(booking)
    audit(booking.requester, "bookings.booking", booking.pk, "booking_submitted", before={"request_status": Booking.RequestStatus.DRAFT}, after={"request_status": booking.request_status})
    return booking


# ---------------------------------------------------------------------------
# หน้าจองแบบ 3 ขั้นในหน้าเดียว (ธีม A): ชิปวัน/ช่วงเวลา, คำแนะนำเวลาอื่น, ค่าผู้รับผิดชอบเดิม
# ทุกฟังก์ชันใช้ validate_booking_window()/find_available_rooms() ชุดเดียวกับการจองจริง
# ไม่มีกฎตรวจชนชุดที่สอง — ฐานข้อมูล (ExclusionConstraint) ยังตัดสินสุดท้ายตอนยื่นคำขอ
# ---------------------------------------------------------------------------

THAI_WEEKDAYS_SHORT = ("จ.", "อ.", "พ.", "พฤ.", "ศ.", "ส.", "อา.")
THAI_MONTHS_SHORT_NO_YEAR = ("", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")
DATE_CHOICE_OTHER = "other"
PERIOD_CHOICE_CUSTOM = "custom"
FEW_ROOMS_THRESHOLD = 3


def short_thai_date(value) -> str:
    """เช่น "จ. 6 ต.ค." — ใช้บนชิปวันที่"""
    return f"{THAI_WEEKDAYS_SHORT[value.weekday()]} {value.day} {THAI_MONTHS_SHORT_NO_YEAR[value.month]}"


def search_date_choices(today=None, weekdays: int = 4) -> list[dict]:
    """ชิปวันที่: วันนี้, พรุ่งนี้ แล้ววันทำการ (จ.–ศ.) ถัดไปอีก `weekdays` วัน"""
    today = today or timezone.localdate()
    tomorrow = today + timedelta(days=1)
    choices = [
        {"value": today.isoformat(), "date": today, "label": "วันนี้", "sub": short_thai_date(today)},
        {"value": tomorrow.isoformat(), "date": tomorrow, "label": "พรุ่งนี้", "sub": short_thai_date(tomorrow)},
    ]
    cursor = tomorrow
    while len(choices) < 2 + weekdays:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            choices.append({"value": cursor.isoformat(), "date": cursor, "label": short_thai_date(cursor), "sub": ""})
    return choices


def search_period_choices() -> list[dict]:
    """ชิปช่วงเวลา มาจากช่วงเวลาสำเร็จรูปที่ผู้ดูแลตั้ง (ReferenceValue) หรือค่า default"""
    return [{"value": f"{preset['start']}-{preset['end']}", **preset} for preset in time_presets()]


@dataclass(frozen=True)
class SearchSelection:
    """ผลแปลงพารามิเตอร์หน้า /book/ (ชิปหรือค่าเดิม date/start/end) เป็นวัน/เวลาที่ใช้ค้นหา"""

    date: date | None
    start_time: str
    end_time: str
    day_choice: str
    period_choice: str
    date_text: str
    error: str = ""

    def _aware(self, hhmm: str) -> datetime | None:
        if self.error or self.date is None:
            return None
        return timezone.make_aware(
            datetime.combine(self.date, time.fromisoformat(hhmm)), timezone.get_current_timezone()
        )

    @property
    def start_at(self) -> datetime | None:
        return self._aware(self.start_time)

    @property
    def end_at(self) -> datetime | None:
        return self._aware(self.end_time)


def _parse_hhmm(value) -> str | None:
    try:
        return datetime.strptime(str(value or "")[:5], "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def resolve_search_selection(params, today=None) -> SearchSelection:
    """แปลงพารามิเตอร์ค้นหาเป็นวัน/เวลา

    - ชิปวัน `day` (ISO) ชนะช่อง `date` · `day=other` หรือไม่มีชิป → ใช้ช่อง `date` (พ.ศ. หรือ ISO)
    - ชิปช่วงเวลา `period=HH:MM-HH:MM` ชนะ `start`/`end` · `period=custom` หรือไม่มี → ใช้ `start`/`end`
    - ลิงก์เดิม (`?date=&start=&end=` จากหน้าแรก) ใช้ได้เหมือนเดิม และระบบเลือกชิปที่ตรงให้เอง
    - ไม่มีอะไรเลย → พรุ่งนี้ ช่วงเวลาแรกของรายการ (เช้า)
    """
    from .forms import BuddhistDateField

    today = today or timezone.localdate()
    date_values = {choice["value"] for choice in search_date_choices(today)}
    periods = {choice["value"]: choice for choice in search_period_choices()}

    error = ""
    day = (params.get("day") or "").strip()
    raw_date = (params.get("date") or "").strip()
    booking_date = None
    if day and day != DATE_CHOICE_OTHER:
        try:
            booking_date = date.fromisoformat(day)
        except ValueError:
            booking_date = None
    if booking_date is None and raw_date:
        try:
            booking_date = BuddhistDateField().clean(raw_date)
        except ValidationError:
            error = "กรุณาตรวจวันที่อีกครั้ง (วัน/เดือน/ปี พ.ศ.)"
    if booking_date is None and not error:
        if day == DATE_CHOICE_OTHER:
            error = "กรุณาระบุวันที่ (วัน/เดือน/ปี พ.ศ.)"
        else:
            booking_date = today + timedelta(days=1)

    period = (params.get("period") or "").strip()
    start_text = _parse_hhmm(params.get("start"))
    end_text = _parse_hhmm(params.get("end"))
    if period in periods:
        start_text, end_text = periods[period]["start"], periods[period]["end"]
    elif not params.get("start") and not params.get("end") and period != PERIOD_CHOICE_CUSTOM and periods:
        first = next(iter(periods.values()))
        start_text, end_text = first["start"], first["end"]
    if (start_text is None or end_text is None) and not error:
        error = "กรุณาตรวจเวลาเริ่มและเวลาสิ้นสุดอีกครั้ง"
    start_text = start_text or "09:00"
    end_text = end_text or "10:00"
    if not error and end_text <= start_text:
        error = "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม"

    key = f"{start_text}-{end_text}"
    period_choice = key if key in periods and period != PERIOD_CHOICE_CUSTOM else PERIOD_CHOICE_CUSTOM
    if booking_date is not None and booking_date.isoformat() in date_values and day != DATE_CHOICE_OTHER:
        day_choice = booking_date.isoformat()
    else:
        day_choice = DATE_CHOICE_OTHER
    date_text = (
        f"{booking_date.day:02d}/{booking_date.month:02d}/{booking_date.year + 543}" if booking_date else raw_date
    )
    return SearchSelection(
        date=booking_date,
        start_time=start_text,
        end_time=end_text,
        day_choice=day_choice,
        period_choice=period_choice,
        date_text=date_text,
        error=error,
    )


def room_day_bookings(rooms, day) -> dict[int, list[Booking]]:
    """การจองที่ถือครองเวลาในวันนั้น แยกตามห้อง (ใช้วาดแถบเวลาเล็กในผลค้นหา)"""
    zone = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(day, time.min), zone)
    day_end = day_start + timedelta(days=1)
    result: dict[int, list[Booking]] = {}
    queryset = (
        Booking.objects.filter(
            room__in=list(rooms),
            request_status__in=Booking.HOLDING_STATUSES,
            start_at__lt=day_end,
            end_at__gt=day_start,
        )
        .exclude(usage_status=Booking.UsageStatus.DISPLACED)
        .only("room_id", "start_at", "end_at", "request_status")
        .order_by("start_at")
    )
    for booking in queryset:
        result.setdefault(booking.room_id, []).append(booking)
    return result


def frequent_rooms(user, room_categories=None, limit: int = 3) -> list[Resource]:
    """ห้องที่ผู้ใช้จองบ่อยที่สุด (นับคำขอที่ยื่นแล้วทุกสถานะ ไม่นับร่าง) — ใช้จัดลำดับคำแนะนำ"""
    from django.db.models import Count, Max

    if not getattr(user, "is_authenticated", False):
        return []
    rows = Booking.objects.filter(
        requester=user, room__resource_type=Resource.Type.ROOM, room__status=Resource.Status.ACTIVE
    ).exclude(request_status=Booking.RequestStatus.DRAFT)
    if room_categories:
        rows = rows.filter(room__room_category__in=tuple(room_categories))
    ranked = (
        rows.values("room_id")
        .annotate(times=Count("id"), last_used=Max("start_at"))
        .order_by("-times", "-last_used")[:limit]
    )
    ids = [row["room_id"] for row in ranked]
    by_id = Resource.objects.select_related("rule").in_bulk(ids)
    return [by_id[pk] for pk in ids if pk in by_id]


def _slot_is_bookable(room: Resource, start: datetime, end: datetime, user, equipment, now) -> bool:
    """ตรวจช่วงเวลาหนึ่งด้วยกฎชุดเดียวกับ find_available_rooms() (กฎรายห้อง + ชนเวลา + อุปกรณ์)"""
    if validate_booking_window(room, start, end, user, now=now):
        return False
    if _active_holds_overlapping(room, compute_hold(room, start, end)).exists():
        return False
    return not any(_active_holds_overlapping(item, compute_hold(item, start, end)).exists() for item in equipment)


def nearest_free_slot(
    room: Resource,
    start: datetime,
    end: datetime,
    user,
    equipment=(),
    now: datetime | None = None,
    step_minutes: int = 15,
    max_checks: int = 16,
) -> tuple[datetime, datetime] | None:
    """ช่วงว่างที่ใกล้เวลาที่ขอที่สุด ความยาวเท่าเดิม วันเดียวกัน ภายในเวลาให้บริการของห้อง

    เรียงผู้สมัครตามระยะเลื่อน (ระยะเท่ากันเลือกเลื่อนไปข้างหลังก่อน) คัดกรองเบื้องต้นด้วยช่วงถือครอง
    ที่ดึงมาครั้งเดียว แล้วยืนยันทุกช่วงด้วย _slot_is_bookable() — กฎเดียวกับการค้นหาปกติ
    (เวลาให้บริการ, ล่วงหน้า, งดใช้/วันหยุด, buffer, สิทธิ์หน่วย, อุปกรณ์ส่วนกลาง)
    """
    now = now or timezone.now()
    duration = end - start
    if duration <= timedelta(0):
        return None
    zone = timezone.get_current_timezone()
    day = timezone.localtime(start).date()
    rule = getattr(room, "rule", None)
    open_at = rule.service_start if rule else time(7, 0)
    close_at = rule.service_end if rule else time(21, 0)
    if isinstance(open_at, str):
        open_at = time.fromisoformat(open_at)
    if isinstance(close_at, str):
        close_at = time.fromisoformat(close_at)
    window_start = timezone.make_aware(datetime.combine(day, open_at), zone)
    window_end = timezone.make_aware(datetime.combine(day, close_at), zone)
    if window_start.minute % step_minutes:  # ฟอร์มรับเฉพาะช่วงละ 15 นาที
        window_start += timedelta(minutes=step_minutes - window_start.minute % step_minutes)

    candidates = []
    cursor = window_start
    while cursor + duration <= window_end:
        if cursor != start and cursor >= now:
            candidates.append(cursor)
        cursor += timedelta(minutes=step_minutes)
    candidates.sort(key=lambda value: (abs(value - start), value < start))

    probe = DateTimeTZRange(window_start - timedelta(hours=3), window_end + timedelta(hours=3), "[)")
    taken = [
        (hold.lower, hold.upper)
        for hold in BookingResource.objects.filter(
            resource=room, released_at__isnull=True, hold__overlap=probe
        ).values_list("hold", flat=True)
    ]
    checks = 0
    for candidate_start in candidates:
        candidate_end = candidate_start + duration
        hold = compute_hold(room, candidate_start, candidate_end)
        if any(hold.lower < upper and lower < hold.upper for lower, upper in taken):
            continue  # คัดออกเร็วเท่านั้น — ช่วงที่ผ่านต้องยืนยันด้วย _slot_is_bookable() เสมอ
        checks += 1
        if _slot_is_bookable(room, candidate_start, candidate_end, user, equipment, now):
            return candidate_start, candidate_end
        if checks >= max_checks:
            break
    return None


def next_available_date(
    start: datetime,
    end: datetime,
    user,
    attendees: int | None = None,
    equipment_codes=(),
    room_categories=None,
    max_days: int = 14,
) -> tuple[datetime, datetime, int] | None:
    """วันทำการถัดไป (จ.–ศ.) ที่มีห้องว่างในเวลาเดียวกัน คืน (เริ่ม, สิ้นสุด, จำนวนห้องว่าง)"""
    zone = timezone.get_current_timezone()
    local_start = timezone.localtime(start)
    local_end = timezone.localtime(end)
    for offset in range(1, max_days + 1):
        day = local_start.date() + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        day_start = timezone.make_aware(datetime.combine(day, local_start.time()), zone)
        day_end = timezone.make_aware(datetime.combine(day, local_end.time()), zone)
        available, _ = find_available_rooms(
            day_start,
            day_end,
            user,
            attendees=attendees,
            equipment_codes=equipment_codes,
            room_categories=room_categories,
        )
        if available:
            return day_start, day_end, len(available)
    return None


@dataclass(frozen=True)
class SlotSuggestion:
    """คำแนะนำเมื่อห้องว่างน้อย: kind="shift" (ห้องเดิม เลื่อนเวลา) หรือ "next_date" (วันอื่น เวลาเดิม)"""

    kind: str
    start_at: datetime
    end_at: datetime
    room: Resource | None = None
    frequent: bool = False
    available_count: int = 0


def booking_suggestions(
    user,
    start: datetime,
    end: datetime,
    available: list[RoomSearchResult],
    unavailable: list[RoomSearchResult],
    attendees: int | None = None,
    equipment_codes=(),
    room_categories=None,
    now: datetime | None = None,
    max_shift_rooms: int = 3,
) -> list[SlotSuggestion]:
    """คำแนะนำเวลาอื่นสำหรับขั้น ๒ (เลือกห้อง)

    (ก) ห้องที่ผู้ใช้จองบ่อยซึ่งไม่ว่าง "เพราะชนเวลาเท่านั้น" → ช่วงว่างที่ใกล้ที่สุดวันเดียวกัน
        ถ้าห้องว่างน้อยกว่า FEW_ROOMS_THRESHOLD ห้อง เพิ่มห้องอื่นที่ชนเวลาเท่านั้นด้วย (สูงสุด max_shift_rooms)
    (ข) ไม่มีห้องว่างเลย → วันทำการถัดไปที่มีห้องว่างในเวลาเดิม
    """
    now = now or timezone.now()
    frequent_ids = [room.pk for room in frequent_rooms(user, room_categories)]
    conflict_only = {result.room.pk: result.room for result in unavailable if result.time_conflict_only}
    candidates = [conflict_only[pk] for pk in frequent_ids if pk in conflict_only]
    if len(available) < FEW_ROOMS_THRESHOLD:
        candidates += [room for pk, room in conflict_only.items() if pk not in frequent_ids]
    equipment = list(
        Resource.objects.filter(
            resource_type=Resource.Type.EQUIPMENT, status=Resource.Status.ACTIVE, code__in=list(equipment_codes)
        ).select_related("rule")
    )
    suggestions: list[SlotSuggestion] = []
    for room in candidates:
        if len(suggestions) >= max_shift_rooms:
            break
        slot = nearest_free_slot(room, start, end, user, equipment=equipment, now=now)
        if slot:
            suggestions.append(SlotSuggestion("shift", slot[0], slot[1], room=room, frequent=room.pk in frequent_ids))
    if not available:
        found = next_available_date(
            start, end, user, attendees=attendees, equipment_codes=equipment_codes, room_categories=room_categories
        )
        if found:
            suggestions.append(SlotSuggestion("next_date", found[0], found[1], available_count=found[2]))
    return suggestions


def last_booking_defaults(user) -> dict:
    """ค่าผู้รับผิดชอบ/โทรศัพท์/หน่วย จากการจองล่าสุดของผู้ใช้ (ยังไม่เคยจอง → จากโปรไฟล์)

    คืนเฉพาะค่าที่ไม่ว่าง พร้อมคีย์ "source" = "last_booking" | "profile"
    """
    defaults = {
        "responsible_name": getattr(user, "display_name", "") or "",
        "responsible_phone": getattr(user, "phone", "") or "",
        "unit": getattr(user, "unit_id", None),
        "source": "profile",
    }
    last = (
        Booking.objects.filter(requester=user)
        .exclude(responsible_name="")
        .only("responsible_name", "responsible_phone", "unit_id")
        .order_by("-created_at")
        .first()
    )
    if last is not None:
        defaults["responsible_name"] = last.responsible_name
        defaults["responsible_phone"] = last.responsible_phone or defaults["responsible_phone"]
        defaults["unit"] = last.unit_id or defaults["unit"]
        defaults["source"] = "last_booking"
    return {key: value for key, value in defaults.items() if value not in (None, "")}


def booking_ref(booking: Booking) -> str:
    """เลขอ้างอิงสั้นที่แสดงให้ผู้ใช้ (8 ตัวแรกของรหัส — ตรงกับ "รหัสการจอง" ในหน้ารายละเอียด)"""
    return str(booking.pk)[:8]

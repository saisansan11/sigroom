"""
กฎธุรกิจของการจอง — view/template ห้ามมีตรรกะเหล่านี้เอง

M0/M1 ครอบคลุม: คำนวณช่วงถือครองรวม buffer (FR-07) และสร้าง/ส่งการจองพร้อมถือครอง
ทรัพยากรภายใต้ exclusion constraint (FR-09) โดยแปลงข้อผิดพลาดของฐานข้อมูลเป็นข้อความไทย
"""
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.utils import timezone

from resources.models import Resource, ResourceRule

from .models import Booking, BookingResource


class BookingConflict(Exception):
    """ทรัพยากรไม่ว่างในช่วงเวลาที่ขอ"""

    def __init__(self, resource: Resource):
        self.resource = resource
        super().__init__(f"{resource.code} {resource.name} ไม่ว่างในช่วงเวลาที่เลือก")


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


def approval_policy_for(booking: Booking) -> str:
    """
    ประเมินนโยบายอนุมัติจากห้องและข้อมูลคำขอ (D1, SRS 12.2)
    - ห้องนโยบาย "ต้องอนุมัติ" → ต้องอนุมัติ
    - มีผู้เข้าร่วมจากภายนอก → ต้องอนุมัติ แม้ห้องเป็นอัตโนมัติ
    """
    rule = getattr(booking.room, "rule", None)
    if rule and rule.approval_policy == ResourceRule.ApprovalPolicy.REQUIRED:
        return ResourceRule.ApprovalPolicy.REQUIRED
    if booking.has_external_attendees:
        return ResourceRule.ApprovalPolicy.REQUIRED
    return ResourceRule.ApprovalPolicy.AUTO


@transaction.atomic
def submit_booking(booking: Booking, equipment: list[Resource] | None = None) -> Booking:
    """
    ส่งคำขอ: ถือครองทรัพยากร แล้วตั้งสถานะตามนโยบาย (อัตโนมัติ → อนุมัติ, ต้องอนุมัติ → รออนุมัติ)
    การทำงานทั้งหมดอยู่ใน transaction เดียว — ถ้าชนจะไม่มีอะไรถูกบันทึก
    """
    if booking.request_status != Booking.RequestStatus.DRAFT:
        raise ValueError("ส่งได้เฉพาะคำขอสถานะร่าง")
    booking.submitted_at = timezone.now()
    policy = approval_policy_for(booking)
    booking.request_status = (
        Booking.RequestStatus.APPROVED if policy == ResourceRule.ApprovalPolicy.AUTO else Booking.RequestStatus.PENDING
    )
    booking.save()
    place_holds(booking, equipment)
    return booking

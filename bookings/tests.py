"""
ทดสอบกฎถือครองทรัพยากร (M1) — ต้องมี PostgreSQL จริง เพราะทดสอบ exclusion constraint ที่ฐานข้อมูล
รัน: uv run pytest
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from bookings.services import BookingConflict, compute_hold, release_holds, submit_booking
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def unit():
    return Unit.objects.create(code="COMM", name="แผนกวิชาการสื่อสาร")


@pytest.fixture
def user(unit):
    return User.objects.create_user(username="somchai", email="somchai@signalschool.ac.th", password="x" * 12, unit=unit)


@pytest.fixture
def room():
    r = Resource.objects.create(code="B2-301", name="ห้องเรียน 301", room_category=Resource.Category.CLASSROOM)
    ResourceRule.objects.create(resource=r)  # อัตโนมัติ buffer 0
    return r


@pytest.fixture
def meeting_room():
    r = Resource.objects.create(code="MTG-1", name="ห้องประชุม 1", room_category=Resource.Category.MEETING)
    ResourceRule.objects.create(resource=r, approval_policy=ResourceRule.ApprovalPolicy.REQUIRED, buffer_before_min=15, buffer_after_min=30)
    return r


@pytest.fixture
def projector():
    r = Resource.objects.create(code="PROJ-05", name="โปรเจกเตอร์พกพา 5", resource_type=Resource.Type.EQUIPMENT, room_category=Resource.Category.NONE)
    ResourceRule.objects.create(resource=r)
    return r


def _booking(user, unit, room, start, hours=1, **kw) -> Booking:
    return Booking.objects.create(
        room=room, requester=user, unit=unit, responsible_name="ร.อ.สมชาย", responsible_phone="081",
        title="วิชาสายอากาศ", start_at=start, end_at=start + timedelta(hours=hours), **kw,
    )


def test_auto_policy_room_is_approved_on_submit(user, unit, room):
    start = timezone.now() + timedelta(days=1)
    b = submit_booking(_booking(user, unit, room, start))
    assert b.request_status == Booking.RequestStatus.APPROVED
    assert b.holds.count() == 1


def test_required_policy_room_is_pending_on_submit(user, unit, meeting_room):
    start = timezone.now() + timedelta(days=1)
    b = submit_booking(_booking(user, unit, meeting_room, start))
    assert b.request_status == Booking.RequestStatus.PENDING


def test_external_attendees_force_approval_even_in_auto_room(user, unit, room):
    start = timezone.now() + timedelta(days=1)
    b = submit_booking(_booking(user, unit, room, start, has_external_attendees=True))
    assert b.request_status == Booking.RequestStatus.PENDING


def test_overlapping_booking_is_rejected_by_database(user, unit, room):
    """FR-09: การจองที่สองที่ชนเวลาต้องถูกปฏิเสธ และไม่มีอะไรถูกบันทึกค้าง"""
    start = timezone.now() + timedelta(days=1)
    submit_booking(_booking(user, unit, room, start, hours=2))
    second = _booking(user, unit, room, start + timedelta(hours=1))
    with pytest.raises(BookingConflict) as exc:
        submit_booking(second)
    assert exc.value.resource == room
    second.refresh_from_db()
    assert second.request_status == Booking.RequestStatus.DRAFT  # transaction ย้อนกลับทั้งหมด
    assert second.holds.count() == 0


def test_adjacent_bookings_do_not_conflict(user, unit, room):
    """ช่วง [) — จบ 10:00 กับเริ่ม 10:00 ไม่ชนกันเมื่อ buffer = 0"""
    start = timezone.now() + timedelta(days=1)
    submit_booking(_booking(user, unit, room, start, hours=1))
    submit_booking(_booking(user, unit, room, start + timedelta(hours=1), hours=1))
    assert Booking.objects.filter(request_status=Booking.RequestStatus.APPROVED).count() == 2


def test_buffer_is_included_in_hold(user, unit, meeting_room):
    """FR-07: buffer 15 ก่อน / 30 หลัง ถูกรวมในช่วงถือครอง และทำให้การจองที่ติดกันชน"""
    start = timezone.now() + timedelta(days=1)
    b = submit_booking(_booking(user, unit, meeting_room, start, hours=1))
    hold = b.holds.get().hold
    assert hold.lower == start - timedelta(minutes=15)
    assert hold.upper == start + timedelta(hours=1, minutes=30)
    with pytest.raises(BookingConflict):
        submit_booking(_booking(user, unit, meeting_room, start + timedelta(hours=1, minutes=10)))


def test_released_hold_frees_the_slot(user, unit, room):
    """FR-10: ยกเลิกแล้วช่วงเวลาว่างให้ผู้อื่น"""
    start = timezone.now() + timedelta(days=1)
    first = submit_booking(_booking(user, unit, room, start))
    first.request_status = Booking.RequestStatus.CANCELLED
    first.save()
    release_holds(first)
    second = submit_booking(_booking(user, unit, room, start))
    assert second.request_status == Booking.RequestStatus.APPROVED


def test_equipment_conflict_reports_which_resource(user, unit, room, meeting_room, projector):
    """FR-06: ห้องต่างกันแต่โปรเจกเตอร์ตัวเดียวกัน → ชนที่โปรเจกเตอร์ และบอกได้ว่าชนที่ไหน"""
    start = timezone.now() + timedelta(days=1)
    submit_booking(_booking(user, unit, room, start), equipment=[projector])
    second = _booking(user, unit, meeting_room, start)
    with pytest.raises(BookingConflict) as exc:
        submit_booking(second, equipment=[projector])
    assert exc.value.resource == projector
    assert second.holds.count() == 0


def test_compute_hold_without_rule_has_no_buffer(room):
    room.rule.delete()
    room = Resource.objects.get(pk=room.pk)
    start = timezone.now()
    hold = compute_hold(room, start, start + timedelta(hours=1))
    assert hold.lower == start and hold.upper == start + timedelta(hours=1)

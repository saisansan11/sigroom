"""Regression coverage for stale cancellation and reservation boundaries."""
from datetime import datetime, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Unit, User
from audit.models import AuditLog
from bookings.amendment_services import submit_amendment
from bookings.lodging_models import CourseLodgingCohort
from bookings.lodging_services import cohort_conflict_for_resource, update_cohort_allocation
from bookings.models import Booking
from bookings.services import (
    BookingConflict, cancel_booking, find_available_rooms, place_holds,
    submit_booking, validate_booking_window,
)
from resources.models import Blackout, Resource, ResourceOutage, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def data():
    unit = Unit.objects.create(code="AUDIT", name="หน่วยทดสอบ")
    user = User.objects.create_user(username="audit-user", unit=unit)
    room = Resource.objects.create(code="AUDIT-1", name="ห้องทดสอบ")
    start = timezone.make_aware(datetime.combine(timezone.localdate() + timedelta(days=7), time(9)))
    booking = Booking.objects.create(
        room=room, requester=user, unit=unit, title="ทดสอบ",
        start_at=start, end_at=start + timedelta(hours=1),
    )
    return user, room, booking


@pytest.mark.parametrize("status", ["cancelled", "rejected", "expired"])
def test_cancel_rejects_stale_terminal_status(data, status):
    user, room, booking = data
    Booking.objects.filter(pk=booking.pk).update(request_status=status, revision=8)
    with pytest.raises(ValueError):
        cancel_booking(booking, user)
    booking.refresh_from_db()
    assert booking.request_status == status
    assert booking.revision == 8
    assert not AuditLog.objects.filter(action="booking_cancelled", entity_id=str(booking.pk)).exists()


def test_cancel_uses_current_deadline(data):
    user, room, booking = data
    now = timezone.now()
    Booking.objects.filter(pk=booking.pk).update(start_at=now + timedelta(hours=1))
    with pytest.raises(PermissionError):
        cancel_booking(booking, user, now=now)
    booking.refresh_from_db()
    assert booking.request_status == Booking.RequestStatus.DRAFT


def test_cancel_preserves_latest_revision_and_releases_holds(data):
    user, room, booking = data
    place_holds(booking)
    Booking.objects.filter(pk=booking.pk).update(request_status="approved", revision=8)
    result = cancel_booking(booking, user)
    assert result.revision == 9
    assert result.request_status == "cancelled"
    assert not result.holds.filter(released_at__isnull=True).exists()


@pytest.mark.parametrize("kind", ["blackout", "outage"])
def test_room_without_rule_still_observes_closures(data, kind):
    user, room, booking = data
    values = dict(start_at=booking.start_at, end_at=booking.end_at)
    if kind == "blackout":
        Blackout.objects.create(title="ปิดทั้งโรงเรียน", **values)
    else:
        ResourceOutage.objects.create(resource=room, created_by=user, reason="ซ่อมห้อง", **values)
    with pytest.raises(ValidationError):
        submit_booking(booking)
    booking.refresh_from_db()
    assert booking.request_status == Booking.RequestStatus.DRAFT
    assert not booking.holds.exists()
    available, unavailable = find_available_rooms(booking.start_at, booking.end_at, user)
    assert not available
    assert unavailable[0].room == room


@pytest.mark.parametrize("side", ["before", "after"])
@pytest.mark.parametrize("overlap", [True, False])
def test_lodging_buffers_respect_cohort_boundaries(data, side, overlap):
    user, room, booking = data
    room.room_category = Resource.Category.LODGING
    room.save(update_fields=["room_category"])
    ResourceRule.objects.create(resource=room, buffer_before_min=30, buffer_after_min=30)
    day = timezone.localdate() + timedelta(days=8)
    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นทดสอบ", slug="audit-cohort", supervisor=user, unit=user.unit,
        check_in_date=day, check_out_date=day,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort.rooms.add(room)
    boundary = timezone.make_aware(datetime.combine(day, time.min))
    gap = timedelta(minutes=15 if overlap else 30)
    if side == "before":
        booking.end_at = boundary - gap
        booking.start_at = booking.end_at - timedelta(hours=1)
    else:
        booking.start_at = boundary + timedelta(days=1) + gap
        booking.end_at = booking.start_at + timedelta(hours=1)
    booking.save()
    assert bool(cohort_conflict_for_resource(room, booking.start_at, booking.end_at)) == overlap
    assert bool(validate_booking_window(room, booking.start_at, booking.end_at, user)) == overlap
    if overlap:
        with pytest.raises(BookingConflict):
            place_holds(booking)
        assert not booking.holds.exists()
    else:
        assert len(place_holds(booking)) == 1

    # Reverse ordering must give the same answer when a cohort is allocated later.
    cohort.allocation_status = CourseLodgingCohort.AllocationStatus.RELEASED
    cohort.save(update_fields=["allocation_status"])
    if overlap:
        place_holds(booking)
    user.is_superuser = True
    user.save(update_fields=["is_superuser"])
    arguments = dict(
        cohort=cohort, rooms=[room], check_in_date=day, check_out_date=day,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=False, beds_per_room=1, actor=user,
    )
    if overlap:
        with pytest.raises(ValidationError):
            update_cohort_allocation(**arguments)
    else:
        update_cohort_allocation(**arguments)


def test_amendment_cannot_move_into_cohort_buffer(data):
    user, room, booking = data
    room.room_category = Resource.Category.LODGING
    room.save(update_fields=["room_category"])
    ResourceRule.objects.create(resource=room, buffer_after_min=30)
    booking.request_status = Booking.RequestStatus.APPROVED
    booking.save()
    original_hold = place_holds(booking)[0]
    day = timezone.localdate() + timedelta(days=9)
    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นทดสอบ", slug="amend-cohort", supervisor=user, unit=user.unit,
        check_in_date=day, check_out_date=day, allocation_status="allocated",
    )
    cohort.rooms.add(room)
    end = timezone.make_aware(datetime.combine(day, time.min)) - timedelta(minutes=15)
    with pytest.raises(ValidationError):
        submit_amendment(booking, user, {
            "start_at": end - timedelta(hours=1), "end_at": end, "reason": "เปลี่ยนเวลา",
        })
    assert not booking.amendments.exists()
    original_hold.refresh_from_db()
    assert original_hold.released_at is None

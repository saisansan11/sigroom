from datetime import datetime, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Unit, User
from approvals.services import run_scheduled_jobs
from audit.models import AuditLog
from bookings.models import Booking
from notifications.models import Notification
from resources.models import Resource, ResourceRule

from .services import set_usage_status


def _aware(day, hour=12):
    return timezone.make_aware(datetime(2026, 8, day, hour), timezone.get_current_timezone())


@pytest.fixture
def usage_setup():
    unit = Unit.objects.create(code="U-M6", name="หน่วยทดสอบ M6")
    requester = User.objects.create_user("m6-requester", "m6-requester@signalschool.ac.th", "Test-Password-123", unit=unit)
    custodian = User.objects.create_user("m6-custodian", "m6-custodian@signalschool.ac.th", "Test-Password-123", unit=unit)
    outsider = User.objects.create_user("m6-outsider", "m6-outsider@signalschool.ac.th", "Test-Password-123", unit=unit)
    room = Resource.objects.create(code="M6-ROOM", name="ห้อง M6", owner_unit=unit)
    ResourceRule.objects.create(resource=room)
    room.custodians.add(custodian)
    return unit, requester, custodian, outsider, room


def _booking(setup, *, end, usage=Booking.UsageStatus.UPCOMING):
    unit, requester, custodian, outsider, room = setup
    return Booking.objects.create(
        room=room, requester=requester, unit=unit, responsible_name="ผู้รับผิดชอบ", responsible_phone="1234",
        title="กิจกรรมทดสอบ", start_at=end - timedelta(hours=2), end_at=end,
        request_status=Booking.RequestStatus.APPROVED, usage_status=usage,
    )


@pytest.mark.django_db
def test_run_jobs_marks_only_finished_upcoming_as_used_and_is_idempotent(usage_setup):
    finished = _booking(usage_setup, end=_aware(20))
    displaced = _booking(usage_setup, end=_aware(20), usage=Booking.UsageStatus.DISPLACED)
    unavailable = _booking(usage_setup, end=_aware(20), usage=Booking.UsageStatus.ROOM_UNAVAILABLE)
    first = run_scheduled_jobs(_aware(21))
    second = run_scheduled_jobs(_aware(21))
    finished.refresh_from_db(); displaced.refresh_from_db(); unavailable.refresh_from_db()
    assert first["usage_used"] == 1 and second["usage_used"] == 0
    assert finished.usage_status == Booking.UsageStatus.USED
    assert displaced.usage_status == Booking.UsageStatus.DISPLACED
    assert unavailable.usage_status == Booking.UsageStatus.ROOM_UNAVAILABLE
    assert AuditLog.objects.filter(entity_id=str(finished.pk), action="usage_status_auto_used").count() == 1


@pytest.mark.django_db
def test_custodian_overrides_used_with_no_show_and_requester_is_notified(usage_setup):
    booking = _booking(usage_setup, end=_aware(20), usage=Booking.UsageStatus.USED)
    set_usage_status(booking, usage_setup[2], Booking.UsageStatus.NO_SHOW, _aware(21))
    booking.refresh_from_db()
    assert booking.usage_status == Booking.UsageStatus.NO_SHOW
    notification = Notification.objects.get(user=usage_setup[1], booking=booking)
    assert "ถูกบันทึกว่าไม่มาใช้" in notification.text
    assert AuditLog.objects.filter(entity_id=str(booking.pk), action="usage_status_changed").exists()


@pytest.mark.django_db
def test_usage_change_rejects_outsider_and_after_three_days(usage_setup):
    booking = _booking(usage_setup, end=_aware(20), usage=Booking.UsageStatus.USED)
    with pytest.raises(PermissionError):
        set_usage_status(booking, usage_setup[3], Booking.UsageStatus.NO_SHOW, _aware(21))
    with pytest.raises(ValidationError):
        set_usage_status(booking, usage_setup[2], Booking.UsageStatus.NO_SHOW, _aware(24))


@pytest.mark.django_db
def test_usage_view_returns_403_for_non_custodian(client, usage_setup):
    booking = _booking(usage_setup, end=_aware(20), usage=Booking.UsageStatus.USED)
    client.force_login(usage_setup[3])
    response = client.post(f"/usage/{booking.pk}/status/", {"status": "no_show"})
    assert response.status_code == 403


from datetime import date, datetime, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from bookings.services import place_holds
from notifications.models import Notification
from notifications.services import notify_submitted, unread_count
from resources.models import Resource, ResourceApprover, ResourceRule

from .models import Approval
from .services import (
    approve_booking,
    can_decide,
    create_delegation,
    pending_for,
    reject_booking,
    run_scheduled_jobs,
    sla_deadline,
)

pytestmark = pytest.mark.django_db


def _aware(year=2026, month=8, day=24, hour=9):
    return timezone.make_aware(datetime(year, month, day, hour), timezone.get_current_timezone())


@pytest.fixture
def setup_m3():
    unit = Unit.objects.create(code="HQ", name="กองบังคับการ")
    users = {
        name: User.objects.create_user(
            username=name,
            email=f"{name}@signalschool.ac.th",
            password="Password-2569",
            unit=unit,
        )
        for name in ("requester", "primary", "backup", "delegate", "outsider")
    }
    room = Resource.objects.create(code="MTG-1", name="ห้องประชุม 1", room_category=Resource.Category.MEETING)
    ResourceRule.objects.create(
        resource=room,
        approval_policy=ResourceRule.ApprovalPolicy.REQUIRED,
        service_start=time(7),
        service_end=time(21),
    )
    ResourceApprover.objects.create(resource=room, user=users["primary"], is_primary=True)
    ResourceApprover.objects.create(resource=room, user=users["backup"], is_primary=False)
    return users, room


def _pending(users, room, *, submitted_at=None, start_at=None, urgent=False, title="แผนลับการฝึก"):
    submitted_at = submitted_at or _aware()
    start_at = start_at or submitted_at + timedelta(days=5)
    booking = Booking.objects.create(
        room=room,
        requester=users["requester"],
        unit=users["requester"].unit,
        responsible_name="ร.อ.สมชาย ใจดี",
        responsible_phone="0810000000",
        title=title,
        start_at=start_at,
        end_at=start_at + timedelta(hours=1),
        request_status=Booking.RequestStatus.PENDING,
        submitted_at=submitted_at,
        is_urgent=urgent,
    )
    place_holds(booking)
    return booking


def test_queue_primary_backup_and_outsider_permissions(client, setup_m3):
    users, room = setup_m3
    booking = _pending(users, room)

    assert pending_for(users["primary"], _aware()) == [booking]
    assert pending_for(users["backup"], _aware()) == []
    client.force_login(users["outsider"])
    denied = client.get(reverse("approvals:queue"))
    assert denied.status_code == 403
    assert "คุณไม่มีสิทธิ์เข้าถึง" in denied.content.decode()
    client.force_login(users["backup"])
    assert client.get(reverse("approvals:queue")).status_code == 200


def test_approve_records_notifies_and_rejects_second_decision(setup_m3):
    users, room = setup_m3
    booking = _pending(users, room)

    approve_booking(booking, users["primary"], _aware())
    booking.refresh_from_db()
    assert booking.request_status == Booking.RequestStatus.APPROVED
    assert Approval.objects.filter(booking=booking, action=Approval.Action.APPROVED, acted_by=users["primary"]).count() == 1
    assert Notification.objects.filter(user=users["requester"], booking=booking).exists()
    with pytest.raises(ValueError, match="ถูกดำเนินการแล้ว"):
        approve_booking(booking, users["primary"], _aware())
    assert Approval.objects.filter(booking=booking, action=Approval.Action.APPROVED).count() == 1


def test_reject_requires_reason_releases_hold_and_shows_reason(client, setup_m3):
    users, room = setup_m3
    booking = _pending(users, room)
    with pytest.raises(ValidationError, match="กรุณาระบุเหตุผล"):
        reject_booking(booking, users["primary"], "", _aware())

    reject_booking(booking, users["primary"], "ห้องติดภารกิจ ผบ.", _aware())
    booking.refresh_from_db()
    assert booking.request_status == Booking.RequestStatus.REJECTED
    assert booking.decision_reason == "ห้องติดภารกิจ ผบ."
    assert not booking.holds.filter(released_at__isnull=True).exists()
    client.force_login(users["requester"])
    assert "ห้องติดภารกิจ ผบ." in client.get(reverse("bookings:booking_detail", args=[booking.pk])).content.decode()
    assert "ห้องติดภารกิจ ผบ." in client.get(reverse("bookings:my_bookings"), {"tab": "closed"}).content.decode()


def test_active_delegation_records_on_behalf_and_overlap_is_rejected(client, setup_m3):
    users, room = setup_m3
    create_delegation(users["primary"], users["delegate"], date(2026, 8, 24), date(2026, 8, 25))
    booking = _pending(users, room)

    assert can_decide(users["delegate"], booking, _aware()) is True
    assert can_decide(users["delegate"], booking, _aware(day=26)) is False
    approve_booking(booking, users["delegate"], _aware())
    action = Approval.objects.get(booking=booking, action=Approval.Action.APPROVED)
    assert action.acted_by == users["delegate"]
    assert action.on_behalf_of == users["primary"]
    client.force_login(users["delegate"])
    history = client.get(reverse("bookings:booking_detail", args=[booking.pk])).content.decode()
    assert "รักษาการแทน" in history
    with pytest.raises(ValidationError, match="ทับซ้อน"):
        create_delegation(users["primary"], users["backup"], date(2026, 8, 25), date(2026, 8, 27))


def test_backup_can_decide_after_sla_or_immediately_when_urgent(setup_m3):
    users, room = setup_m3
    booking = _pending(users, room, submitted_at=_aware())
    assert sla_deadline(booking) == _aware(day=26)
    assert can_decide(users["backup"], booking, _aware(day=25)) is False
    assert can_decide(users["backup"], booking, _aware(day=26)) is True

    urgent = _pending(users, room, start_at=_aware(day=30), urgent=True)
    assert can_decide(users["backup"], urgent, _aware()) is True


def test_jobs_expire_normal_notice_but_wait_until_start_for_short_notice(setup_m3):
    users, room = setup_m3
    normal = _pending(
        users,
        room,
        submitted_at=_aware(day=24),
        start_at=_aware(day=27, hour=10),
    )
    short_room = Resource.objects.create(code="MTG-2", name="ห้องประชุม 2")
    ResourceRule.objects.create(resource=short_room, approval_policy=ResourceRule.ApprovalPolicy.REQUIRED)
    ResourceApprover.objects.create(resource=short_room, user=users["primary"], is_primary=True)
    short = _pending(
        users,
        short_room,
        submitted_at=_aware(day=27, hour=10),
        start_at=_aware(day=28, hour=6),
        urgent=True,
    )

    run_scheduled_jobs(_aware(day=26, hour=11))
    normal.refresh_from_db()
    short.refresh_from_db()
    assert normal.request_status == Booking.RequestStatus.EXPIRED
    assert not normal.holds.filter(released_at__isnull=True).exists()
    assert short.request_status == Booking.RequestStatus.PENDING
    run_scheduled_jobs(_aware(day=28, hour=6))
    short.refresh_from_db()
    assert short.request_status == Booking.RequestStatus.EXPIRED


def test_jobs_are_idempotent_for_expiry(setup_m3):
    users, room = setup_m3
    booking = _pending(users, room, submitted_at=_aware(day=24), start_at=_aware(day=26, hour=10))
    now = _aware(day=25, hour=11)

    first = run_scheduled_jobs(now)
    approval_count = Approval.objects.filter(booking=booking).count()
    notification_count = Notification.objects.filter(booking=booking).count()
    second = run_scheduled_jobs(now)
    assert first["expired"] == 1 and second["expired"] == 0
    assert Approval.objects.filter(booking=booking).count() == approval_count
    assert Notification.objects.filter(booking=booking).count() == notification_count


def test_sla_escalates_once_and_notifies_backup(setup_m3):
    users, room = setup_m3
    booking = _pending(users, room, submitted_at=_aware(day=24), start_at=_aware(day=30))
    now = _aware(day=26)

    first = run_scheduled_jobs(now)
    backup_notifications = Notification.objects.filter(user=users["backup"], booking=booking).count()
    second = run_scheduled_jobs(now)
    booking.refresh_from_db()
    assert booking.sla_escalated_at == now
    assert first["escalated"] == 1 and second["escalated"] == 0
    assert Notification.objects.filter(user=users["backup"], booking=booking).count() == backup_notifications == 1


def test_notifications_read_scope_and_never_include_title(client, setup_m3):
    users, room = setup_m3
    booking = _pending(users, room, title="ชื่อกิจกรรมลับมาก")
    notify_submitted(booking)
    assert unread_count(users["requester"]) == 1
    assert not Notification.objects.filter(text__contains=booking.title).exists()
    item = Notification.objects.get(user=users["requester"])

    client.force_login(users["outsider"])
    assert client.get(reverse("notifications:open", args=[item.pk])).status_code == 404
    client.force_login(users["requester"])
    assert client.get(reverse("notifications:open", args=[item.pk])).status_code == 302
    item.refresh_from_db()
    assert item.read_at is not None
    assert unread_count(users["requester"]) == 0

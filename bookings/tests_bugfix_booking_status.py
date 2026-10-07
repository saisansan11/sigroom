"""Regression: สถานะการจองหลังบังคับย้าย/งดใช้ห้อง/หมดอายุ และปฏิทิน (ตรวจบัค 30 ก.ย. 2569)"""
from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.amendment_services import submit_amendment
from bookings.models import Booking, BookingAmendment
from bookings.preemption_services import execute_preemption
from bookings.services import cancel_booking, place_holds
from resources.models import Resource, ResourceApprover, ResourceRule
from resources.services import affected_bookings, create_outage, end_outage_early

pytestmark = pytest.mark.django_db


def _local(day_offset, hour):
    day = timezone.localdate() + timedelta(days=day_offset)
    return timezone.make_aware(datetime.combine(day, time(hour)), timezone.get_current_timezone())


@pytest.fixture
def env():
    unit = Unit.objects.create(code="COMM", name="แผนกวิชาการสื่อสาร")
    requester = User.objects.create_user(
        username="req", email="req@signalschool.ac.th", password="Password-2569", unit=unit
    )
    primary = User.objects.create_user(
        username="pri", email="pri@signalschool.ac.th", password="Password-2569", unit=unit, position="ผอ.กวส."
    )
    admin = User.objects.create_superuser(username="adm", email="adm@signalschool.ac.th", password="Password-2569")
    room = Resource.objects.create(code="B1-201", name="ห้อง 201", capacity=40, owner_unit=unit)
    ResourceRule.objects.create(resource=room, service_start=time(7), service_end=time(21))
    ResourceApprover.objects.create(resource=room, user=primary, is_primary=True)
    room.custodians.add(primary)
    start = _local(5, 9)
    booking = Booking.objects.create(
        room=room, requester=requester, unit=unit, responsible_name="ร.อ.ทดสอบ",
        responsible_phone="0810000000", title="วิชาเดิม", start_at=start, end_at=start + timedelta(hours=2),
        attendees=10, request_status=Booking.RequestStatus.APPROVED, submitted_at=timezone.now(),
    )
    place_holds(booking)
    return {"unit": unit, "requester": requester, "primary": primary, "admin": admin, "room": room, "booking": booking}


def _preempt(env):
    return execute_preemption(
        env["booking"], env["primary"], "ภารกิจเร่งด่วน", "กห 0001/69",
        {"title": "งานเข้าแทน", "unit": env["unit"], "responsible_name": "ผอ.กวส.", "responsible_phone": "0800000000"},
        None,
    )


def _outage_around(env, booking):
    return create_outage(
        env["room"], env["primary"], booking.start_at - timedelta(hours=1), booking.end_at + timedelta(hours=1), "ซ่อมแอร์"
    )


def test_outage_keeps_displaced_status_and_end_early_does_not_revive_it(env):
    preemption = _preempt(env)
    displaced = env["booking"]

    outage, affected = _outage_around(env, displaced)
    displaced.refresh_from_db()
    assert displaced.usage_status == Booking.UsageStatus.DISPLACED
    assert displaced not in affected
    assert preemption.incoming in affected  # งานที่เข้าแทนยังได้รับผลกระทบตามปกติ

    end_outage_early(outage, env["primary"])
    displaced.refresh_from_db()
    assert displaced.usage_status == Booking.UsageStatus.DISPLACED
    assert not displaced.holds.filter(released_at__isnull=True).exists()


def test_outage_does_not_overwrite_recorded_usage(env):
    booking = env["booking"]
    Booking.objects.filter(pk=booking.pk).update(usage_status=Booking.UsageStatus.USED)
    assert list(affected_bookings(env["room"], booking.start_at, booking.end_at)) == []
    _outage_around(env, booking)
    booking.refresh_from_db()
    assert booking.usage_status == Booking.UsageStatus.USED


def test_end_outage_early_does_not_restore_cancelled_booking(env):
    booking = env["booking"]
    outage, _ = _outage_around(env, booking)
    cancel_booking(Booking.objects.get(pk=booking.pk), env["requester"])
    restored = end_outage_early(outage, env["primary"])
    booking.refresh_from_db()
    assert booking not in restored
    assert booking.usage_status == Booking.UsageStatus.ROOM_UNAVAILABLE


def test_outage_then_end_early_still_restores_normal_booking(env):
    booking = env["booking"]
    outage, affected = _outage_around(env, booking)
    assert booking in affected
    restored = end_outage_early(outage, env["primary"])
    booking.refresh_from_db()
    assert booking in restored
    assert booking.usage_status == Booking.UsageStatus.UPCOMING


def test_displaced_booking_hidden_from_calendar_feed(env, client):
    preemption = _preempt(env)
    displaced = env["booking"]
    client.force_login(env["requester"])
    response = client.get(
        reverse("bookings:calendar_events"),
        {"start": (displaced.start_at - timedelta(days=1)).isoformat(), "end": (displaced.end_at + timedelta(days=1)).isoformat()},
    )
    ids = [event.get("id") for event in response.json()]
    assert str(displaced.pk) not in ids
    assert str(preemption.incoming.pk) in ids


def test_displaced_booking_not_shown_as_next_booking(env, client):
    _preempt(env)
    client.force_login(env["requester"])
    response = client.get(reverse("bookings:calendar"))
    assert response.context["next_booking"] is None


def test_my_bookings_labels_displaced_booking(env, client):
    _preempt(env)
    client.force_login(env["requester"])
    html = client.get(reverse("bookings:my_bookings")).content.decode()
    assert 'status-displaced">ถูกย้าย' in html


def test_displaced_booking_not_on_today_board(env, client):
    start = timezone.localtime(timezone.now()).replace(hour=18, minute=0, second=0, microsecond=0)
    booking = env["booking"]
    Booking.objects.filter(pk=booking.pk).update(start_at=start, end_at=start + timedelta(hours=1))
    booking.holds.update(released_at=timezone.now())
    Booking.objects.filter(pk=booking.pk).update(usage_status=Booking.UsageStatus.DISPLACED)
    client.force_login(env["requester"])
    response = client.get(reverse("bookings:room_status", args=["classroom"]))
    row = next(row for row in response.context["board_rows"] if row["room"] == env["room"])
    assert all(block["label"] != "วิชาเดิม" for block in row["blocks"])


def test_requester_can_cancel_when_admin_filed_pending_amendment(env):
    booking = env["booking"]
    submit_amendment(booking, env["admin"], {"has_external": True, "external_note": "ทบ. 5 นาย", "reason": "มีแขก"})
    amendment = booking.amendments.get(status=BookingAmendment.Status.PENDING)

    cancel_booking(Booking.objects.get(pk=booking.pk), env["requester"])

    booking.refresh_from_db()
    amendment.refresh_from_db()
    assert booking.request_status == Booking.RequestStatus.CANCELLED
    assert amendment.status == BookingAmendment.Status.WITHDRAWN
    assert not amendment.holds.filter(released_at__isnull=True).exists()


def test_unrelated_user_still_cannot_withdraw_amendment(env, client):
    booking = env["booking"]
    submit_amendment(booking, env["admin"], {"has_external": True, "external_note": "ทบ. 5 นาย", "reason": "มีแขก"})
    amendment = booking.amendments.get(status=BookingAmendment.Status.PENDING)
    client.force_login(env["primary"])
    client.post(reverse("bookings:amendment_withdraw", args=[amendment.pk]))
    amendment.refresh_from_db()
    assert amendment.status == BookingAmendment.Status.PENDING


def test_expired_future_booking_only_in_closed_tab(env, client):
    booking = env["booking"]
    Booking.objects.filter(pk=booking.pk).update(request_status=Booking.RequestStatus.EXPIRED)
    client.force_login(env["requester"])
    groups = client.get(reverse("bookings:my_bookings")).context["groups"]
    assert booking not in list(groups["upcoming"])
    assert booking in list(groups["closed"])


def test_calendar_feed_ignores_out_of_range_dates(env, client):
    response = client.get(
        reverse("bookings:calendar_events"), {"start": "2026-13-45T00:00:00", "end": "2026-02-30T00:00:00"}
    )
    assert response.status_code == 200

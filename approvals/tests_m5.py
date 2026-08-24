from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from accounts.models import Unit, User
from approvals.services import run_scheduled_jobs
from bookings.amendment_services import amendment_expiry_deadline, submit_amendment
from bookings.models import Booking, BookingAmendment, Preemption
from bookings.services import place_holds
from notifications.models import Notification
from resources.models import Resource, ResourceApprover, ResourceRule

pytestmark = pytest.mark.django_db


def _aware(day, hour=9):
    return timezone.make_aware(datetime(2026, 8, day, hour), timezone.get_current_timezone())


@pytest.fixture
def jobs_setup():
    unit = Unit.objects.create(code="COMM-J", name="แผนกวิชาการสื่อสาร")
    requester = User.objects.create_user(username="jobrequester", email="jobrequester@signalschool.ac.th", password="x", unit=unit)
    approver = User.objects.create_user(username="jobapprover", email="jobapprover@signalschool.ac.th", password="x", unit=unit)
    room = Resource.objects.create(code="MTG-J", name="ห้องประชุมงานระบบ", capacity=30)
    ResourceRule.objects.create(
        resource=room, approval_policy=ResourceRule.ApprovalPolicy.REQUIRED,
        service_start=time(7), service_end=time(21),
    )
    ResourceApprover.objects.create(resource=room, user=approver, is_primary=True)
    booking = Booking.objects.create(
        room=room, requester=requester, unit=unit, responsible_name="ผู้รับผิดชอบ", responsible_phone="081",
        title="กิจกรรมเดิม", start_at=_aware(30), end_at=_aware(30, 11), attendees=10,
        request_status=Booking.RequestStatus.APPROVED, submitted_at=_aware(24),
    )
    place_holds(booking)
    amendment = submit_amendment(
        booking,
        requester,
        {"room": room, "start_at": _aware(29), "end_at": _aware(29, 11), "equipment": [],
         "attendees": 10, "has_external": False, "external_note": ""},
        _aware(24),
    )
    return unit, requester, approver, room, booking, amendment


def test_amendment_expiry_uses_earlier_start_and_is_idempotent(jobs_setup):
    _, requester, _, _, _, amendment = jobs_setup
    BookingAmendment.objects.filter(pk=amendment.pk).update(submitted_at=_aware(24))
    amendment.refresh_from_db()
    assert amendment_expiry_deadline(amendment) == _aware(28)
    first = run_scheduled_jobs(_aware(28))
    notifications = Notification.objects.filter(user=requester).count()
    second = run_scheduled_jobs(_aware(28))
    amendment.refresh_from_db()
    assert amendment.status == BookingAmendment.Status.EXPIRED
    assert first["amendment_expired"] == 1 and second["amendment_expired"] == 0
    assert Notification.objects.filter(user=requester).count() == notifications


def test_amendment_sla_escalates_once(jobs_setup):
    _, _, _, _, _, amendment = jobs_setup
    BookingAmendment.objects.filter(pk=amendment.pk).update(submitted_at=_aware(24))
    first = run_scheduled_jobs(_aware(26, 10))
    second = run_scheduled_jobs(_aware(26, 10))
    amendment.refresh_from_db()
    assert amendment.sla_escalated_at == _aware(26, 10)
    assert first["amendment_escalated"] == 1 and second["amendment_escalated"] == 0


def test_preemption_deemed_acknowledged_after_24_hours_once(jobs_setup):
    _, requester, approver, room, booking, amendment = jobs_setup
    amendment.status = BookingAmendment.Status.WITHDRAWN
    amendment.save(update_fields=["status"])
    incoming = Booking.objects.create(
        room=room, requester=approver, unit=requester.unit, responsible_name="ผู้รับผิดชอบ", responsible_phone="082",
        title="งานเข้าแทน", start_at=_aware(30), end_at=_aware(30, 11),
        request_status=Booking.RequestStatus.APPROVED,
    )
    preemption = Preemption.objects.create(
        displaced=booking, incoming=incoming, ordered_by=approver, ordered_by_position="ผู้อนุมัติหลัก",
        reference_no="กห 009", reason="ภารกิจ",
    )
    Preemption.objects.filter(pk=preemption.pk).update(created_at=_aware(24))
    first = run_scheduled_jobs(_aware(25))
    notices = Notification.objects.filter(user=approver).count()
    second = run_scheduled_jobs(_aware(25))
    preemption.refresh_from_db()
    assert preemption.deemed_acknowledged is True
    assert first["deemed_acknowledged"] == 1 and second["deemed_acknowledged"] == 0
    assert Notification.objects.filter(user=approver).count() == notices

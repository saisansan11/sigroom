from datetime import date, datetime, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import Unit, User
from approvals.models import Approval
from approvals.services import decide_series, run_scheduled_jobs, sla_deadline
from bookings.models import Booking, BookingSeries
from bookings.series_services import create_series
from notifications.models import Notification
from resources.models import Blackout, Resource, ResourceApprover, ResourceRule

pytestmark = pytest.mark.django_db


def _aware(day, hour=9):
    return timezone.make_aware(datetime(2026, 8, day, hour), timezone.get_current_timezone())


@pytest.fixture
def approval_series_setup():
    unit = Unit.objects.create(code="HQ", name="กองบังคับการ")
    requester = User.objects.create_user(
        username="requester", email="requester@signalschool.ac.th", password="Password-2569", unit=unit
    )
    approver = User.objects.create_user(
        username="approver", email="approver@signalschool.ac.th", password="Password-2569", unit=unit
    )
    room = Resource.objects.create(code="MTG-1", name="ห้องประชุม 1")
    ResourceRule.objects.create(
        resource=room,
        approval_policy=ResourceRule.ApprovalPolicy.REQUIRED,
        service_start=time(7),
        service_end=time(21),
    )
    ResourceApprover.objects.create(resource=room, user=approver, is_primary=True)
    return requester, approver, room


def _template(user, room, title="ประชุมลับชุดใหญ่"):
    booking = Booking(
        room=room,
        requester=user,
        unit=user.unit,
        responsible_name="ร.อ.สมชาย",
        responsible_phone="081",
        title=title,
        start_at=_aware(28),
        end_at=_aware(28, 10),
    )
    booking._series_equipment = []
    return booking


def _params(start=date(2026, 8, 28), count=3):
    return {
        "freq": BookingSeries.Frequency.WEEKLY,
        "weekdays": [start.weekday()],
        "custom_dates": [],
        "start_date": start,
        "end_date": None,
        "requested_count": count,
        "time_start": time(9),
        "time_end": time(10),
    }


def test_decide_series_approves_all_except_selected_with_reason(approval_series_setup):
    requester, approver, room = approval_series_setup
    series = create_series(room, _params(), _template(requester, room), requester, now=_aware(24))
    excluded = series.occurrences.order_by("start_at")[1]

    result = decide_series(
        series,
        approver,
        "approve",
        [excluded.pk],
        reason_excluded="ติดภารกิจหน่วย",
        now=_aware(24),
    )
    excluded.refresh_from_db()
    assert result == {"approved": 2, "rejected": 1}
    assert excluded.request_status == Booking.RequestStatus.REJECTED
    assert excluded.decision_reason == "ติดภารกิจหน่วย"
    assert not excluded.holds.filter(released_at__isnull=True).exists()
    assert series.occurrences.filter(request_status=Booking.RequestStatus.APPROVED).count() == 2
    assert Notification.objects.filter(user=requester, text__contains="อนุมัติ 2").count() == 1
    assert not Notification.objects.filter(text__contains="ประชุมลับชุดใหญ่").exists()


def test_decide_series_rejects_whole_series_and_repeated_decision_fails(approval_series_setup):
    requester, approver, room = approval_series_setup
    series = create_series(room, _params(), _template(requester, room), requester, now=_aware(24))

    result = decide_series(series, approver, "reject", reason_reject="ห้องติดภารกิจ", now=_aware(24))
    assert result == {"approved": 0, "rejected": 3}
    assert series.occurrences.filter(request_status=Booking.RequestStatus.REJECTED).count() == 3
    assert Approval.objects.filter(booking__series=series, action=Approval.Action.REJECTED).count() == 3
    with pytest.raises(ValueError, match="ถูกดำเนินการแล้ว"):
        decide_series(series, approver, "reject", reason_reject="ซ้ำ", now=_aware(24))


def test_decide_series_requires_reason_for_excluded_occurrence(approval_series_setup):
    requester, approver, room = approval_series_setup
    series = create_series(room, _params(), _template(requester, room), requester, now=_aware(24))
    excluded = series.occurrences.first()
    with pytest.raises(ValidationError, match="เหตุผลของครั้งที่ตัดออก"):
        decide_series(series, approver, "approve", [excluded.pk], now=_aware(24))
    assert series.occurrences.filter(request_status=Booking.RequestStatus.PENDING).count() == 3


def test_series_expires_together_and_job_is_idempotent(approval_series_setup):
    requester, _, room = approval_series_setup
    series = create_series(room, _params(), _template(requester, room), requester, now=_aware(24))
    now = _aware(27, 10)
    before_notifications = Notification.objects.filter(user=requester).count()

    first = run_scheduled_jobs(now)
    after_first = Notification.objects.filter(user=requester).count()
    second = run_scheduled_jobs(now)
    assert first["expired"] == 3 and second["expired"] == 0
    assert series.occurrences.filter(request_status=Booking.RequestStatus.EXPIRED).count() == 3
    assert not series.occurrences.filter(holds__released_at__isnull=True).exists()
    assert after_first == before_notifications + 1
    assert Notification.objects.filter(user=requester).count() == after_first


def test_sla_skips_all_room_blackout_day(approval_series_setup):
    requester, _, room = approval_series_setup
    booking = Booking.objects.create(
        room=room,
        requester=requester,
        unit=requester.unit,
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="081",
        title="คำขอเดี่ยว",
        start_at=_aware(31),
        end_at=_aware(31, 10),
        request_status=Booking.RequestStatus.PENDING,
        submitted_at=_aware(24),
    )
    Blackout.objects.create(
        title="วันหยุดราชการ",
        start_at=_aware(25, 0),
        end_at=_aware(26, 0),
        scope=Blackout.Scope.ALL,
    )
    assert sla_deadline(booking) == _aware(27)

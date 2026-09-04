from datetime import date, datetime, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from approvals.services import pending_for
from bookings.models import Booking, BookingSeries, SeriesSkip
from bookings.series_services import (
    cancel_remaining,
    create_series,
    generate_occurrence_dates,
    preview_series,
)
from bookings.services import cancel_booking, place_holds
from resources.models import Blackout, Resource, ResourceApprover, ResourceRule

pytestmark = pytest.mark.django_db


def _aware(day, hour=9):
    return timezone.make_aware(datetime(2026, 8, day, hour), timezone.get_current_timezone())


@pytest.fixture
def m4_setup():
    unit = Unit.objects.create(code="COMM", name="แผนกวิชาการสื่อสาร")
    requester = User.objects.create_user(
        username="somchai", email="somchai@signalschool.ac.th", password="Password-2569", unit=unit
    )
    approver = User.objects.create_user(
        username="wanida", email="wanida@signalschool.ac.th", password="Password-2569", unit=unit
    )
    room = Resource.objects.create(code="B1-201", name="ห้องเรียน 201", building="อาคาร 1")
    rule = ResourceRule.objects.create(
        resource=room,
        approval_policy=ResourceRule.ApprovalPolicy.AUTO,
        service_start=time(7),
        service_end=time(21),
        max_series_occurrences=20,
    )
    return requester, approver, room, rule


def _template(user, room, title="วิชาสายอากาศ"):
    booking = Booking(
        room=room,
        requester=user,
        unit=user.unit,
        responsible_name="ร.อ.สมชาย ใจดี",
        responsible_phone="0810000000",
        title=title,
        start_at=_aware(24),
        end_at=_aware(24, 10),
    )
    booking._series_equipment = []
    return booking


def _params(**overrides):
    values = {
        "freq": BookingSeries.Frequency.WEEKLY,
        "weekdays": [0, 2],
        "custom_dates": [],
        "start_date": date(2026, 8, 24),
        "end_date": None,
        "requested_count": 4,
        "time_start": time(9),
        "time_end": time(10),
    }
    values.update(overrides)
    return values


def test_generate_weekly_dates_and_enforce_rule_limits(m4_setup):
    _, _, _, rule = m4_setup
    dates = generate_occurrence_dates(_params(requested_count=8), rule)
    assert len(dates) == 8
    assert dates[0].weekday() == 0 and dates[1].weekday() == 2
    with pytest.raises(ValidationError, match="ไม่เกิน 20"):
        generate_occurrence_dates(_params(requested_count=21), rule)
    rule.allow_series = False
    rule.save(update_fields=["allow_series"])
    with pytest.raises(ValidationError, match="ไม่อนุญาต"):
        generate_occurrence_dates(_params(), rule)


def test_preview_reports_masked_conflict_and_building_blackout(m4_setup):
    requester, _, room, _ = m4_setup
    other_unit = Unit.objects.create(code="EW", name="แผนกวิชา EW")
    other = User.objects.create_user(
        username="other", email="other@signalschool.ac.th", password="Password-2569", unit=other_unit
    )
    collision = Booking.objects.create(
        room=room,
        requester=other,
        unit=other_unit,
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="081",
        title="กิจกรรมที่มองไม่เห็น",
        start_at=_aware(24),
        end_at=_aware(24, 10),
        request_status=Booking.RequestStatus.APPROVED,
        submitted_at=_aware(23),
    )
    place_holds(collision)
    Blackout.objects.create(
        title="พิธีส่วนกลาง",
        start_at=_aware(26, 0),
        end_at=_aware(27, 0),
        scope=Blackout.Scope.BUILDING,
        building="อาคาร 1",
    )

    preview = preview_series(room, _params(), _template(requester, room), requester, now=_aware(23))
    assert preview.items[0].status == "conflict"
    assert "กิจกรรมที่มองไม่เห็น" not in preview.items[0].reason
    assert preview.items[1].status == "blackout"
    assert preview.items[1].reason == "พิธีส่วนกลาง"


def test_create_series_keeps_free_dates_and_turns_new_collision_into_skip(m4_setup):
    requester, _, room, _ = m4_setup
    collision = Booking.objects.create(
        room=room,
        requester=requester,
        unit=requester.unit,
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="081",
        title="รายการแทรก",
        start_at=_aware(26),
        end_at=_aware(26, 10),
        request_status=Booking.RequestStatus.APPROVED,
        submitted_at=_aware(23),
    )
    place_holds(collision)

    params = _params(preview_free_dates=["2026-08-24", "2026-08-26", "2026-08-31", "2026-09-02"])
    series = create_series(room, params, _template(requester, room), requester, now=_aware(23))
    assert series.occurrences.count() == 3
    skip = series.skips.get(occur_date=date(2026, 8, 26))
    assert skip.kind == SeriesSkip.Kind.CONFLICT_AT_SUBMIT
    assert set(series.occurrences.values_list("request_status", flat=True)) == {Booking.RequestStatus.APPROVED}


def test_required_series_is_pending_and_queue_has_one_card(client, m4_setup):
    requester, approver, room, rule = m4_setup
    rule.approval_policy = ResourceRule.ApprovalPolicy.REQUIRED
    rule.save(update_fields=["approval_policy"])
    ResourceApprover.objects.create(resource=room, user=approver, is_primary=True)

    series = create_series(room, _params(), _template(requester, room), requester, now=_aware(23))
    assert set(series.occurrences.values_list("request_status", flat=True)) == {Booking.RequestStatus.PENDING}
    queue = pending_for(approver, _aware(23))
    assert len(queue) == 1
    assert queue[0].is_series_card is True
    assert len(queue[0].series_occurrences) == 4
    client.force_login(approver)
    response = client.get(reverse("approvals:queue"))
    assert response.status_code == 200
    assert "อนุมัติทั้งชุด" in response.content.decode()


def test_cancel_one_occurrence_and_then_remaining(m4_setup):
    requester, _, room, _ = m4_setup
    series = create_series(room, _params(), _template(requester, room), requester, now=_aware(23))
    occurrences = list(series.occurrences.order_by("start_at"))
    cancel_booking(occurrences[0], requester, now=_aware(23))
    assert series.occurrences.exclude(pk=occurrences[0].pk).filter(request_status=Booking.RequestStatus.APPROVED).count() == 3

    result = cancel_remaining(series, requester, now=_aware(23))
    assert result["cancelled"] == 3
    assert series.occurrences.filter(request_status=Booking.RequestStatus.CANCELLED).count() == 4


def test_series_preview_create_and_detail_pages_render(client, m4_setup):
    requester, _, room, _ = m4_setup
    start = timezone.localdate() + timedelta(days=7)
    if start.weekday() >= 5:
        start += timedelta(days=7 - start.weekday())
    data = {
        "date": start.isoformat(),
        "start_time": "09:00",
        "end_time": "10:00",
        "title": "ชุดทดสอบหน้าจอ",
        "purpose": Booking.Purpose.TEACHING,
        "unit": str(requester.unit_id),
        "responsible_name": "ร.อ.สมชาย",
        "responsible_phone": "081",
        "attendees": "10",
        "attendee_level": "",
        "layout": "",
        "has_external_attendees": "False",
        "external_attendees_note": "",
        "visibility": Booking.Visibility.NORMAL,
        "note": "",
        "is_series": "on",
        "series_freq": BookingSeries.Frequency.WEEKLY,
        "series_weekdays": [str(start.weekday())],
        "series_end_mode": "count",
        "series_count": "2",
        "series_custom_dates": "",
    }
    client.force_login(requester)
    preview = client.post(reverse("bookings:series_preview", args=[room.code]), data)
    assert preview.status_code == 200
    assert "ตรวจสอบก่อนยืนยัน" in preview.content.decode()
    data["_preview_free_dates"] = [start.isoformat(), (start + timedelta(days=7)).isoformat()]
    created = client.post(reverse("bookings:series_create", args=[room.code]), data)
    assert created.status_code == 302
    series = BookingSeries.objects.get(created_by=requester)
    detail = client.get(reverse("bookings:series_detail", args=[series.pk]))
    assert detail.status_code == 200
    assert "ชุดการจอง" in detail.content.decode()

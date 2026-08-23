"""เทสกฎและเส้นทาง M2: ค้นหา จอง ยกเลิก การมองเห็น และแก้ไข"""
from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from bookings.services import (
    cancel_booking,
    find_available_rooms,
    submit_booking,
    validate_booking_window,
)
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def units():
    hq = Unit.objects.create(code="HQ", name="กองบังคับการ")
    comm = Unit.objects.create(code="COMM", name="แผนกวิชาการสื่อสาร", parent=hq)
    ew = Unit.objects.create(code="EW", name="แผนกวิชาสงครามอิเล็กทรอนิกส์", parent=hq)
    return {"HQ": hq, "COMM": comm, "EW": ew}


@pytest.fixture
def users(units):
    return {
        code: User.objects.create_user(
            username=code.lower(),
            email=f"{code.lower()}@signalschool.ac.th",
            password="Password-2569",
            unit=unit,
        )
        for code, unit in units.items()
    }


def _room(code="B1-201", *, policy=ResourceRule.ApprovalPolicy.AUTO, before=0, after=0):
    room = Resource.objects.create(code=code, name=f"ห้อง {code}", capacity=30)
    ResourceRule.objects.create(
        resource=room,
        approval_policy=policy,
        buffer_before_min=before,
        buffer_after_min=after,
        service_start=time(7, 0),
        service_end=time(21, 0),
    )
    return room


def _at(day_offset=7, hour=10, minute=0):
    target = timezone.localdate() + timedelta(days=day_offset)
    return timezone.make_aware(datetime.combine(target, time(hour, minute)), timezone.get_current_timezone())


def _booking(user, room, start, *, visibility=Booking.Visibility.NORMAL):
    return Booking.objects.create(
        room=room,
        requester=user,
        unit=user.unit,
        responsible_name="ร.อ.สมชาย ใจดี",
        responsible_phone="0810000000",
        title="วิชาสายอากาศ",
        start_at=start,
        end_at=start + timedelta(hours=1),
        visibility=visibility,
    )


def _post_data(user, start, **overrides):
    data = {
        "date": start.date().isoformat(),
        "start_time": start.strftime("%H:%M"),
        "end_time": (start + timedelta(hours=1)).strftime("%H:%M"),
        "title": "วิชาสายอากาศ",
        "purpose": Booking.Purpose.TEACHING,
        "unit": str(user.unit_id),
        "responsible_name": "ร.อ.สมชาย ใจดี",
        "responsible_phone": "0810000000",
        "attendees": "20",
        "attendee_level": "นนส. รุ่น 60",
        "layout": "แถวหน้ากระดาน",
        "has_external_attendees": "False",
        "external_attendees_note": "",
        "visibility": Booking.Visibility.NORMAL,
        "note": "",
        "action": "submit",
    }
    data.update(overrides)
    return data


def test_find_available_rooms_respects_room_buffer(users):
    room = _room("MTG-1", before=15, after=30)
    start = _at()
    submit_booking(_booking(users["COMM"], room, start))

    available, unavailable = find_available_rooms(
        start + timedelta(hours=1, minutes=15),
        start + timedelta(hours=2),
        users["COMM"],
    )

    assert room not in [result.room for result in available]
    assert room in [result.room for result in unavailable]


def test_allowed_units_filter_room(users, units):
    room = _room("MTG-CO")
    room.rule.allowed_units.set([units["HQ"]])
    start = _at()

    comm_available, _ = find_available_rooms(start, start + timedelta(hours=1), users["COMM"])
    hq_available, _ = find_available_rooms(start, start + timedelta(hours=1), users["HQ"])

    assert room not in [result.room for result in comm_available]
    assert room in [result.room for result in hq_available]


def test_validate_booking_window_reports_advance_duration_and_slot(users):
    room = _room()
    now = _at(day_offset=0, hour=9)

    advance_errors = validate_booking_window(room, now + timedelta(days=91), now + timedelta(days=91, hours=1), users["COMM"], now=now)
    short_errors = validate_booking_window(room, now + timedelta(days=1), now + timedelta(days=1, minutes=20), users["COMM"], now=now)
    slot_errors = validate_booking_window(room, now + timedelta(days=1, minutes=7), now + timedelta(days=1, hours=1), users["COMM"], now=now)

    assert any("90 วัน" in item for item in advance_errors)
    assert any("อย่างน้อย 30 นาที" in item for item in short_errors)
    assert any("15 นาที" in item for item in slot_errors)


def test_post_submit_succeeds_with_hold(client, users):
    room = _room()
    start = _at()
    client.force_login(users["COMM"])

    response = client.post(reverse("bookings:book_form", args=[room.code]), _post_data(users["COMM"], start))

    booking = Booking.objects.get()
    assert response.status_code == 302
    assert booking.request_status == Booking.RequestStatus.APPROVED
    assert booking.holds.count() == 1


def test_post_conflict_returns_form_without_holding_booking(client, users):
    room = _room()
    start = _at()
    submit_booking(_booking(users["COMM"], room, start))
    client.force_login(users["COMM"])

    response = client.post(reverse("bookings:book_form", args=[room.code]), _post_data(users["COMM"], start))

    assert response.status_code == 200
    assert "ไม่ว่าง" in response.content.decode()
    assert Booking.objects.filter(request_status__in=Booking.HOLDING_STATUSES).count() == 1


def test_cancel_before_cutoff_releases_hold_and_after_cutoff_fails(users):
    room = _room()
    start = _at()
    booking = submit_booking(_booking(users["COMM"], room, start))

    cancel_booking(booking, users["COMM"], now=start - timedelta(hours=5))
    booking.refresh_from_db()
    assert booking.request_status == Booking.RequestStatus.CANCELLED
    assert not booking.holds.filter(released_at__isnull=True).exists()

    late = submit_booking(_booking(users["COMM"], room, start + timedelta(days=1)))
    with pytest.raises(PermissionError):
        cancel_booking(late, users["COMM"], now=late.start_at - timedelta(hours=2))


@pytest.mark.parametrize("visibility, expected", [(Booking.Visibility.NORMAL, "ไม่ว่าง — แผนกวิชาการสื่อสาร"), (Booking.Visibility.RESTRICTED, "ไม่ว่าง")])
def test_cross_unit_sees_masked_detail_and_calendar_label(client, users, visibility, expected):
    room = _room()
    booking = submit_booking(_booking(users["COMM"], room, _at(), visibility=visibility))
    client.force_login(users["EW"])

    detail = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    events = client.get(reverse("bookings:calendar_events"), {"start": _at(-1).isoformat(), "end": _at(30).isoformat()}).json()

    html = detail.content.decode()
    assert detail.status_code == 200 and "วิชาสายอากาศ" not in html
    assert events[0]["title"] == expected


def test_approved_edit_ignores_time_but_changes_title(client, users):
    room = _room()
    booking = submit_booking(_booking(users["COMM"], room, _at()))
    original_start = booking.start_at
    client.force_login(users["COMM"])
    data = _post_data(users["COMM"], _at(day_offset=8), title="ชื่อกิจกรรมใหม่")

    response = client.post(reverse("bookings:booking_edit", args=[booking.id]), data)

    booking.refresh_from_db()
    assert response.status_code == 302
    assert booking.start_at == original_start
    assert booking.title == "ชื่อกิจกรรมใหม่"
    assert booking.revision == 2


def test_required_booking_with_30_hours_notice_is_urgent(users, monkeypatch):
    room = _room(policy=ResourceRule.ApprovalPolicy.REQUIRED)
    now = timezone.make_aware(datetime(2026, 8, 24, 9, 0), timezone.get_current_timezone())
    start = now + timedelta(hours=30)
    monkeypatch.setattr("bookings.services.timezone.now", lambda: now)

    booking = submit_booking(_booking(users["COMM"], room, start))

    assert booking.request_status == Booking.RequestStatus.PENDING
    assert booking.is_urgent is True

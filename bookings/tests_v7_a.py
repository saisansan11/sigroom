from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from bookings.services import (
    find_available_now,
    next_quarter_start,
    remember_requester_phone,
    submit_booking,
)
from resources.models import Blackout, Resource, ResourceOutage, ResourceRule


pytestmark = pytest.mark.django_db


@pytest.fixture
def availability_setup():
    unit = Unit.objects.create(code="V7A-EDU", name="หน่วยทดสอบงาน A")
    other_unit = Unit.objects.create(code="V7A-OTHER", name="หน่วยอื่น")
    user = User.objects.create_user(
        username="v7a-user",
        email="v7a-user@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )

    def make_room(code, category, allowed_units=()):
        room = Resource.objects.create(
            code=code,
            name=f"ห้อง {code}",
            resource_type=Resource.Type.ROOM,
            room_category=category,
            building="อาคารทดสอบ",
            capacity=20,
            owner_unit=unit,
        )
        rule = ResourceRule.objects.create(
            resource=room,
            service_start=time(7),
            service_end=time(21),
        )
        if allowed_units:
            rule.allowed_units.set(allowed_units)
        return room

    teaching_rooms = [
        make_room(f"V7A-C{i}", Resource.Category.CLASSROOM)
        for i in range(5)
    ]
    meeting_room = make_room("V7A-M1", Resource.Category.MEETING)
    lodging_room = make_room("V7A-L1", Resource.Category.LODGING)
    restricted_room = make_room("V7A-R1", Resource.Category.CLASSROOM, [other_unit])
    return user, teaching_rooms, meeting_room, lodging_room, restricted_room


def _aware(year=2026, month=9, day=5, hour=10, minute=7, second=12):
    return timezone.make_aware(
        datetime(year, month, day, hour, minute, second),
        timezone.get_current_timezone(),
    )


def test_next_quarter_start_rounds_strictly_to_next_slot():
    assert next_quarter_start(_aware()).strftime("%H:%M") == "10:15"
    assert next_quarter_start(_aware(minute=15, second=0)).strftime("%H:%M") == "10:30"


def test_find_available_now_groups_limits_and_excludes_lodging_and_restricted(availability_setup, monkeypatch):
    user, teaching_rooms, meeting_room, lodging_room, restricted_room = availability_setup
    monkeypatch.setattr("bookings.services.timezone.now", lambda: _aware())

    result = find_available_now(user, now=_aware())
    groups = {group["key"]: group for group in result.groups}

    assert result.start_at.strftime("%H:%M") == "10:15"
    assert result.end_at.strftime("%H:%M") == "11:15"
    assert len(groups["teaching"]["rooms"]) == 4
    assert meeting_room in [item.room for item in groups["meeting"]["rooms"]]
    assert lodging_room not in [item.room for group in result.groups for item in group["rooms"]]
    assert restricted_room not in [item.room for item in groups["teaching"]["rooms"]]
    assert {item.room.pk for item in groups["teaching"]["rooms"]} <= {
        room.pk for room in teaching_rooms
    }


def test_find_available_now_reuses_conflict_blackout_and_outage_checks(availability_setup, monkeypatch):
    user, teaching_rooms, _, _, _ = availability_setup
    now = _aware()
    start = _aware(hour=10, minute=15, second=0)
    end = start + timedelta(hours=1)
    monkeypatch.setattr("bookings.services.timezone.now", lambda: now)

    held = Booking.objects.create(
        room=teaching_rooms[0],
        requester=user,
        unit=user.unit,
        responsible_name=user.display_name,
        responsible_phone="0812345678",
        title="มีคนจองแล้ว",
        start_at=start,
        end_at=end,
    )
    submit_booking(held)

    blackout = Blackout.objects.create(
        title="กิจกรรมส่วนกลาง",
        start_at=start,
        end_at=end,
        scope=Blackout.Scope.ROOMS,
        created_by=user,
    )
    blackout.rooms.add(teaching_rooms[1])
    ResourceOutage.objects.create(
        resource=teaching_rooms[2],
        start_at=start,
        end_at=end,
        reason="ซ่อมบำรุง",
        created_by=user,
    )

    result = find_available_now(user, now=now)
    visible_codes = {
        item.room.code
        for group in result.groups
        for item in group["rooms"]
    }
    assert teaching_rooms[0].code not in visible_codes
    assert teaching_rooms[1].code not in visible_codes
    assert teaching_rooms[2].code not in visible_codes
    assert teaching_rooms[3].code in visible_codes
    assert teaching_rooms[4].code in visible_codes


def test_homepage_book_now_link_prefills_next_slot(client, availability_setup):
    user, teaching_rooms, _, _, _ = availability_setup
    client.force_login(user)

    response = client.get(reverse("bookings:calendar"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "home-entry-grid" in content
    assert f"/book/{teaching_rooms[0].code}/?search=1" in content
    assert "start=09%3A00" not in content


def _booking_post_data(user, start, **overrides):
    data = {
        "date": start.date().isoformat(),
        "start_time": start.strftime("%H:%M"),
        "end_time": (start + timedelta(hours=1)).strftime("%H:%M"),
        "title": "กิจกรรมจากปุ่มจองเลย",
        "purpose": Booking.Purpose.TEACHING,
        "unit": str(user.unit_id),
        "responsible_name": user.display_name,
        "responsible_phone": "0812345678",
        "attendees": "5",
        "attendee_level": "ทดสอบ",
        "layout": "แถวหน้ากระดาน",
        "has_external_attendees": "False",
        "external_attendees_note": "",
        "visibility": Booking.Visibility.NORMAL,
        "note": "",
        "action": "submit",
    }
    data.update(overrides)
    return data


def test_homepage_book_now_submit_conflict_shows_retry_message(client, availability_setup):
    user, teaching_rooms, _, _, _ = availability_setup
    room = teaching_rooms[0]
    start = _aware(day=6, hour=10, minute=15, second=0)
    held = Booking.objects.create(
        room=room,
        requester=user,
        unit=user.unit,
        responsible_name=user.display_name,
        responsible_phone="0812345678",
        title="มีคนจองแทรก",
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    submit_booking(held)
    client.force_login(user)

    homepage = client.get(reverse("bookings:calendar"))
    assert f"/book/{room.code}/?search=1" in homepage.content.decode()

    response = client.post(
        reverse("bookings:book_form", args=[room.code]),
        _booking_post_data(user, start),
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "กรุณาเลือกเวลาหรือห้องอื่น" in content
    assert "ข้อมูลที่กรอกยังอยู่ครบ" in content
    assert Booking.objects.filter(request_status__in=Booking.HOLDING_STATUSES).count() == 1


def test_past_start_shows_shift_button_and_resubmits_next_quarter(client, availability_setup, monkeypatch):
    user, teaching_rooms, _, _, _ = availability_setup
    room = teaching_rooms[0]
    now = _aware(day=5, hour=14, minute=37, second=0)
    monkeypatch.setattr("bookings.services.timezone.now", lambda: now)
    client.force_login(user)

    response = client.post(
        reverse("bookings:book_form", args=[room.code]),
        _booking_post_data(user, _aware(day=5, hour=14, minute=15, second=0)),
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "เวลาเริ่มต้องไม่อยู่ในอดีต" in content
    assert "เลื่อนเป็นช่วงถัดไปและส่งซ้ำ" in content

    retry = client.post(
        reverse("bookings:book_form", args=[room.code]),
        _booking_post_data(
            user,
            _aware(day=5, hour=14, minute=15, second=0),
            action="shift_next_slot",
        ),
    )

    assert retry.status_code == 302
    booking = Booking.objects.get()
    assert timezone.localtime(booking.start_at).strftime("%H:%M") == "14:45"
    assert timezone.localtime(booking.end_at).strftime("%H:%M") == "15:45"


def test_submit_booking_remembers_phone_only_when_profile_is_blank(availability_setup):
    user, teaching_rooms, _, _, _ = availability_setup
    room = teaching_rooms[0]
    start = _aware(day=6, hour=10, minute=0, second=0)
    booking = Booking.objects.create(
        room=room,
        requester=user,
        unit=user.unit,
        responsible_name=user.display_name,
        responsible_phone="0812345678",
        title="กิจกรรมงาน A",
        start_at=start,
        end_at=start + timedelta(hours=1),
    )
    submit_booking(booking)

    user.refresh_from_db()
    assert user.phone == "0812345678"

    user.phone = "0899999999"
    user.save(update_fields=["phone"])
    another = Booking(
        requester=user,
        responsible_phone="0800000000",
    )
    remember_requester_phone(another)
    user.refresh_from_db()
    assert user.phone == "0899999999"

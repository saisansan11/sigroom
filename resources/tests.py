from datetime import datetime, time

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from bookings.services import place_holds, validate_booking_window
from notifications.models import Notification
from resources.models import Blackout, Resource, ResourceOutage, ResourceRule
from resources.services import active_blackouts, create_outage, end_outage_early

pytestmark = pytest.mark.django_db


def _aware(day, hour=9):
    return timezone.make_aware(datetime(2026, 8, day, hour), timezone.get_current_timezone())


@pytest.fixture
def resource_setup():
    unit = Unit.objects.create(code="COMM", name="แผนกวิชาการสื่อสาร")
    custodian = User.objects.create_user(
        username="custodian", email="custodian@signalschool.ac.th", password="Password-2569", unit=unit
    )
    requester = User.objects.create_user(
        username="requester", email="requester@signalschool.ac.th", password="Password-2569", unit=unit
    )
    outsider = User.objects.create_user(
        username="outsider", email="outsider@signalschool.ac.th", password="Password-2569", unit=unit
    )
    room = Resource.objects.create(
        code="LAB-COMM", name="ห้องปฏิบัติการสื่อสาร", building="อาคาร 2", room_category=Resource.Category.LAB
    )
    other = Resource.objects.create(
        code="B1-201", name="ห้องเรียน 201", building="อาคาร 1", room_category=Resource.Category.CLASSROOM
    )
    for item in (room, other):
        ResourceRule.objects.create(resource=item, service_start=time(7), service_end=time(21))
    room.custodians.add(custodian)
    return custodian, requester, outsider, room, other


def test_blackout_all_four_scopes_apply_only_to_target_rooms(resource_setup):
    _, _, _, lab, classroom = resource_setup
    common = {"start_at": _aware(25, 0), "end_at": _aware(26, 0)}
    all_rooms = Blackout.objects.create(title="ทุกห้อง", scope=Blackout.Scope.ALL, **common)
    building = Blackout.objects.create(title="เฉพาะอาคาร 2", scope=Blackout.Scope.BUILDING, building="อาคาร 2", **common)
    category = Blackout.objects.create(title="เฉพาะห้องเรียน", scope=Blackout.Scope.CATEGORY, room_category=Resource.Category.CLASSROOM, **common)
    selected = Blackout.objects.create(title="ห้องที่เลือก", scope=Blackout.Scope.ROOMS, **common)
    selected.rooms.add(classroom)

    assert all_rooms.applies_to(lab) and all_rooms.applies_to(classroom)
    assert building.applies_to(lab) and not building.applies_to(classroom)
    assert category.applies_to(classroom) and not category.applies_to(lab)
    assert selected.applies_to(classroom) and not selected.applies_to(lab)
    assert {item.title for item in active_blackouts(lab, _aware(25), _aware(25, 10))} == {"ทุกห้อง", "เฉพาะอาคาร 2"}


def test_outage_flags_existing_booking_blocks_new_booking_and_restores(resource_setup):
    custodian, requester, _, room, _ = resource_setup
    booking = Booking.objects.create(
        room=room,
        requester=requester,
        unit=requester.unit,
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="081",
        title="กิจกรรมลับในห้อง",
        start_at=_aware(27),
        end_at=_aware(27, 10),
        request_status=Booking.RequestStatus.APPROVED,
        submitted_at=_aware(24),
    )
    place_holds(booking)

    outage, affected = create_outage(room, custodian, _aware(26), _aware(28), "ซ่อมเครื่องปรับอากาศ")
    booking.refresh_from_db()
    assert affected == [booking]
    assert booking.usage_status == Booking.UsageStatus.ROOM_UNAVAILABLE
    assert booking.holds.filter(released_at__isnull=True).exists()
    assert "ห้องงดใช้: ซ่อมเครื่องปรับอากาศ" in validate_booking_window(
        room, _aware(27, 11), _aware(27, 12), requester, now=_aware(24)
    )
    assert Notification.objects.filter(user=requester).count() == 1
    assert not Notification.objects.filter(text__contains=booking.title).exists()

    restored = end_outage_early(outage, custodian, now=_aware(25))
    booking.refresh_from_db()
    assert restored == [booking]
    assert booking.usage_status == Booking.UsageStatus.UPCOMING


def test_outage_page_allows_custodian_and_denies_other_user(client, resource_setup):
    custodian, _, outsider, room, _ = resource_setup
    client.force_login(outsider)
    denied = client.get(reverse("resources:outage", args=[room.code]))
    assert denied.status_code == 403
    client.force_login(custodian)
    allowed = client.get(reverse("resources:outage", args=[room.code]))
    assert allowed.status_code == 200
    assert "ตั้งงดใช้ชั่วคราว" in allowed.content.decode()


def test_calendar_returns_blackout_and_selected_room_outage_as_background(client, resource_setup):
    custodian, requester, _, room, _ = resource_setup
    Blackout.objects.create(
        title="วันหยุดส่วนกลาง",
        start_at=_aware(25, 0),
        end_at=_aware(26, 0),
        scope=Blackout.Scope.ALL,
    )
    ResourceOutage.objects.create(
        resource=room,
        start_at=_aware(26),
        end_at=_aware(27),
        reason="ซ่อมแอร์",
        created_by=custodian,
    )
    client.force_login(requester)
    events = client.get(
        reverse("bookings:calendar_events"),
        {"start": _aware(24).isoformat(), "end": _aware(28).isoformat(), "room": room.code},
    ).json()
    backgrounds = {item["title"]: item for item in events if item.get("display") == "background"}
    assert "วันหยุดส่วนกลาง (ทุกห้อง)" in backgrounds
    assert "งดใช้: ซ่อมแอร์" in backgrounds


def test_resource_rule_rejects_cross_midnight_service_hours(resource_setup):
    room = resource_setup[3]
    rule = room.rule
    rule.service_start = time(22, 0)
    rule.service_end = time(6, 0)
    with pytest.raises(ValidationError):
        rule.full_clean()

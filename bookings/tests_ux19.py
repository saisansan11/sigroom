"""UX-19 Booking Edit Time Preset Parity regression tests."""
from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from bookings.services import time_presets
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def ux19_setup():
    unit = Unit.objects.create(code="UX19", name="หน่วยทดสอบ UX-19")
    owner = User.objects.create_user(
        username="ux19-owner",
        email="ux19-owner@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.อ.",
        first_name="ผู้จอง",
        last_name="ทดสอบ",
        phone="0811111111",
    )
    outsider = User.objects.create_user(
        username="ux19-outsider",
        email="ux19-outsider@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.ท.",
        first_name="ผู้ใช้",
        last_name="อื่น",
        phone="0822222222",
    )
    room = Resource.objects.create(
        code="UX19-R1",
        name="ห้องทดสอบ UX-19",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.CLASSROOM,
        building="อาคารทดสอบ",
        capacity=30,
        owner_unit=unit,
    )
    ResourceRule.objects.create(
        resource=room,
        approval_policy=ResourceRule.ApprovalPolicy.AUTO,
        service_start=time(7, 0),
        service_end=time(21, 0),
        cancel_cutoff_hours=4,
    )

    start = (timezone.now() + timedelta(days=3)).replace(hour=9, minute=0, second=0, microsecond=0)

    def make_booking(*, status):
        return Booking.objects.create(
            room=room,
            requester=owner,
            unit=unit,
            responsible_name="ร.อ. ผู้จอง ทดสอบ",
            responsible_phone="0811111111",
            title="กิจกรรม UX-19",
            purpose=Booking.Purpose.TEACHING,
            start_at=start,
            end_at=start + timedelta(hours=1),
            attendees=20,
            request_status=status,
        )

    return {
        "unit": unit,
        "owner": owner,
        "outsider": outsider,
        "room": room,
        "make_booking": make_booking,
    }


def test_draft_edit_renders_time_presets_and_editable_datetime_fields(client, ux19_setup):
    booking = ux19_setup["make_booking"](status=Booking.RequestStatus.DRAFT)
    client.force_login(ux19_setup["owner"])

    response = client.get(reverse("bookings:booking_edit", args=[booking.id]))

    assert response.status_code == 200
    assert response.context["time_presets"] == time_presets()
    assert {"date", "start_time", "end_time"}.issubset(response.context["form"].fields)
    content = response.content.decode()
    assert 'class="time-preset-row"' in content
    assert 'class="time-preset-button"' in content
    assert 'name="start_time"' in content
    assert 'name="end_time"' in content


def test_post_submit_edit_keeps_datetime_locked_and_hides_presets(client, ux19_setup):
    booking = ux19_setup["make_booking"](status=Booking.RequestStatus.APPROVED)
    client.force_login(ux19_setup["owner"])

    response = client.get(reverse("bookings:booking_edit", args=[booking.id]))

    assert response.status_code == 200
    assert not {"date", "start_time", "end_time"}.intersection(response.context["form"].fields)
    content = response.content.decode()
    assert "time-preset-button" not in content
    assert "คำขอแก้ไข" in content
    assert reverse("bookings:booking_amend", args=[booking.id]) in content


def test_booking_edit_still_denies_non_owner(client, ux19_setup):
    booking = ux19_setup["make_booking"](status=Booking.RequestStatus.DRAFT)
    client.force_login(ux19_setup["outsider"])

    response = client.get(reverse("bookings:booking_edit", args=[booking.id]))

    assert response.status_code == 403


def test_post_submit_edit_ignores_injected_datetime_values(client, ux19_setup):
    booking = ux19_setup["make_booking"](status=Booking.RequestStatus.APPROVED)
    original_start = booking.start_at
    original_end = booking.end_at
    client.force_login(ux19_setup["owner"])

    response = client.post(
        reverse("bookings:booking_edit", args=[booking.id]),
        {
            "title": "กิจกรรม UX-19 แก้ไขแล้ว",
            "responsible_name": "ร.อ. ผู้จอง ทดสอบ",
            "responsible_phone": "0811111111",
            "attendees": "20",
            "date": "30/09/2569",
            "start_time": "15:00",
            "end_time": "16:00",
        },
    )

    booking.refresh_from_db()
    assert response.status_code == 302
    assert booking.title == "กิจกรรม UX-19 แก้ไขแล้ว"
    assert booking.start_at == original_start
    assert booking.end_at == original_end
    assert booking.revision == 2

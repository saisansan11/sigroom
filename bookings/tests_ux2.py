"""UX-2 Express Booking presentation contracts."""
from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def ux2_setup():
    unit = Unit.objects.create(code="UX2", name="หน่วยทดสอบ UX-2")
    user = User.objects.create_user(
        username="ux2_complete",
        email="ux2_complete@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.อ.",
        first_name="พร้อม",
        last_name="จอง",
        phone="081-234-5678",
    )
    incomplete = User.objects.create_user(
        username="ux2_incomplete",
        email="ux2_incomplete@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.ท.",
        first_name="ข้อมูล",
        last_name="ไม่ครบ",
        phone="",
    )
    room = Resource.objects.create(
        code="UX2-101",
        name="ห้อง Express",
        building="อาคาร UX",
        floor="1",
        capacity=40,
    )
    ResourceRule.objects.create(
        resource=room,
        approval_policy=ResourceRule.ApprovalPolicy.AUTO,
        service_start=time(7, 0),
        service_end=time(21, 0),
        allow_series=True,
        max_series_occurrences=10,
    )
    return {"unit": unit, "user": user, "incomplete": incomplete, "room": room}


def _booking_query(days=2):
    return {
        "search": "1",
        "date": (timezone.localdate() + timedelta(days=days)).isoformat(),
        "start": "09:00",
        "end": "10:00",
        "attendees": "12",
    }


def _responsible_tag(html):
    marker = 'class="booking-responsible-details"'
    assert marker in html
    return html.split(marker, 1)[1].split(">", 1)[0]


def test_complete_profile_collapses_responsible_section_but_keeps_fields(client, ux2_setup):
    client.force_login(ux2_setup["user"])
    response = client.get(reverse("bookings:book_form", args=[ux2_setup["room"].code]), _booking_query())
    assert response.status_code == 200
    html = response.content.decode()

    assert "booking-form-express" in html
    assert "booking-selection-summary" in html
    assert "booking-express-layout" in html
    assert "booking-review-compact" in html
    assert "open" not in _responsible_tag(html)
    assert 'name="unit"' in html
    assert 'name="responsible_name"' in html
    assert 'name="responsible_phone"' in html
    assert ux2_setup["user"].display_name in html
    assert ux2_setup["user"].phone in html


def test_incomplete_profile_opens_responsible_section(client, ux2_setup):
    client.force_login(ux2_setup["incomplete"])
    response = client.get(reverse("bookings:book_form", args=[ux2_setup["room"].code]), _booking_query())
    assert response.status_code == 200
    html = response.content.decode()

    assert "open" in _responsible_tag(html)
    assert "ยังไม่มีเบอร์โทร" in html


def test_bound_responsible_error_forces_section_open(client, ux2_setup):
    user = ux2_setup["user"]
    unit = ux2_setup["unit"]
    room = ux2_setup["room"]
    client.force_login(user)
    day = timezone.localdate() + timedelta(days=3)

    response = client.post(
        reverse("bookings:book_form", args=[room.code]),
        {
            "date": day.isoformat(),
            "start_time": "09:00",
            "end_time": "10:00",
            "title": "ทดสอบ Express",
            "purpose": "teaching",
            "unit": str(unit.pk),
            "responsible_name": user.display_name,
            "responsible_phone": "",
            "attendees": "12",
            "has_external_attendees": "False",
            "visibility": "normal",
            "action": "submit",
        },
    )
    assert response.status_code == 200
    html = response.content.decode()

    assert "open" in _responsible_tag(html)
    assert 'data-field-id="id_responsible_phone"' in html
    assert 'name="responsible_phone"' in html


def test_express_form_keeps_primary_draft_and_series_actions(client, ux2_setup):
    client.force_login(ux2_setup["user"])
    response = client.get(reverse("bookings:book_form", args=[ux2_setup["room"].code]), _booking_query())
    assert response.status_code == 200
    html = response.content.decode()

    assert "ขั้นที่ 3 จาก 5 · Express Booking" in html
    assert "บันทึกร่าง" in html
    assert "ยืนยันและส่งคำขอ" in html
    assert "ตรวจสอบชุดการจอง →" in html
    assert "เปลี่ยนเวลา/ห้อง ←" in html


def test_change_room_link_preserves_search_query(client, ux2_setup):
    client.force_login(ux2_setup["user"])
    query = _booking_query()
    response = client.get(reverse("bookings:book_form", args=[ux2_setup["room"].code]), query)
    assert response.status_code == 200
    html = response.content.decode()

    assert 'class="summary-change-link"' in html
    assert "search=1" in html
    assert "start=09%3A00" in html or "start=09:00" in html
    assert "attendees=12" in html


def test_ux2_css_contracts():
    from django.conf import settings
    from pathlib import Path

    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert "/* ===== UX-2 Express Booking ===== */" in css
    assert ".booking-express-layout" in css
    assert ".booking-express-review-column" in css
    assert ".booking-responsible-summary" in css
    assert "max(44px, 2.75rem)" in css

def test_responsible_disclosure_has_enter_keyboard_bridge():
    from django.conf import settings
    from pathlib import Path

    template = (Path(settings.BASE_DIR) / "templates" / "bookings" / "book_form.html").read_text(encoding="utf-8")
    assert "responsibleSummary.addEventListener('keydown'" in template
    assert "event.key === 'Enter'" in template
    assert "responsibleSummary.click()" in template

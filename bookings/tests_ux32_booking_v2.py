"""UX-32 task-first introduction, booking flow V2, and navigation cleanup."""
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def ux32_setup():
    unit = Unit.objects.create(code="UX32", name="หน่วยทดสอบ UX-32")
    user = User.objects.create_user(
        username="ux32-user",
        email="ux32-user@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        phone="0812345678",
        first_name="ผู้ใช้",
        last_name="ทดสอบ UX32",
    )

    def room(code, name, category):
        item = Resource.objects.create(
            code=code,
            name=name,
            resource_type=Resource.Type.ROOM,
            room_category=category,
            status=Resource.Status.ACTIVE,
            capacity=20,
            building="อาคารทดสอบ",
            floor=1,
        )
        ResourceRule.objects.create(resource=item)
        return item

    return {
        "user": user,
        "classroom": room("UX32-CLASS", "ห้องเรียน UX32", Resource.Category.CLASSROOM),
        "meeting": room("UX32-MEET", "ห้องประชุม UX32", Resource.Category.MEETING),
        "lab": room("UX32-LAB", "ห้องปฏิบัติ UX32", Resource.Category.LAB),
        "online": room("UX32-ONLINE", "ห้องสอนออนไลน์ UX32", Resource.Category.ONLINE),
        "lodging": room("UX32-DORM", "ห้องพัก UX32", Resource.Category.LODGING),
    }


def _search_params(**extra):
    params = {
        "search": "1",
        "date": (timezone.localdate() + timedelta(days=2)).isoformat(),
        "start": "09:00",
        "end": "10:00",
    }
    params.update(extra)
    return params


def test_about_page_is_public_and_task_first(client):
    response = client.get(reverse("bookings:about"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "จองห้องและที่พักให้จบในไม่กี่ขั้นตอน" in html
    assert "จองห้องพัก" in html
    assert "ห้องสอนออนไลน์" in html
    assert reverse("bookings:lodging_index") in html


def test_authenticated_home_has_two_primary_task_cards(client, ux32_setup):
    client.force_login(ux32_setup["user"])
    response = client.get(reverse("bookings:calendar"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "home-primary-actions" in html
    assert "จองห้องเรียนหรือห้องประชุม" in html
    assert "จองห้องพัก / ดูรอบหลักสูตร" in html
    assert reverse("bookings:book_search") in html
    assert reverse("bookings:lodging_index") in html


def test_navigation_has_no_duplicate_online_link_and_clear_booking_label():
    template = (Path(settings.BASE_DIR) / "templates" / "base.html").read_text(encoding="utf-8")
    exact_online_url = "{% url 'bookings:online_teaching_home' %}"
    assert template.count(exact_online_url) == 1
    assert "จองห้องเรียน" in template
    assert "รู้จัก SIGROOM" in template


def test_generic_booking_search_excludes_online_and_lodging(client, ux32_setup):
    client.force_login(ux32_setup["user"])
    response = client.get(reverse("bookings:book_search"), _search_params())
    assert response.status_code == 200
    html = response.content.decode()
    assert "UX32-CLASS" in html
    assert "UX32-MEET" in html
    assert "UX32-LAB" in html
    assert "UX32-ONLINE" not in html
    assert "UX32-DORM" not in html


def test_generic_booking_category_filter_reduces_result_noise(client, ux32_setup):
    client.force_login(ux32_setup["user"])
    response = client.get(reverse("bookings:book_search"), _search_params(category="meeting"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "UX32-MEET" in html
    assert "UX32-CLASS" not in html
    assert "UX32-LAB" not in html


def test_booking_v2_uses_progressive_disclosure_for_custom_time(client, ux32_setup):
    client.force_login(ux32_setup["user"])
    response = client.get(reverse("bookings:book_search"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "booking-path-switcher" in html
    assert "booking-category-choice" in html
    assert "booking-date-shortcuts" in html
    assert 'class="booking-custom-time"' in html
    assert "กำหนดเวลาเอง" in html
    assert "time-preset-button" in html
    search_template = (Path(settings.BASE_DIR) / "templates" / "bookings" / "book_search.html").read_text(encoding="utf-8")
    assert "ตัวเลือกเพิ่มเติม · อุปกรณ์ส่วนกลาง" in search_template
    assert "{% if equipment %}" in search_template


def test_mobile_workspace_actions_have_touch_target_contract():
    template = (Path(settings.BASE_DIR) / "templates" / "lodging" / "workspace.html").read_text(encoding="utf-8")
    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert template.count('class="lodging-workspace-link"') >= 3
    assert ".lodging-workspace-link" in css
    block = css.split(".lodging-workspace-link {", 1)[1].split("}", 1)[0]
    assert "min-height: max(44px, 2.75rem)" in block
    equipment_summary = css.rsplit(".search-equipment-summary {", 1)[1].split("}", 1)[0]
    assert "min-height: max(44px, 2.75rem)" in equipment_summary


def test_ux32_css_has_mobile_single_column_contract():
    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert "/* UX-32 Task-first intro, booking flow V2, navigation cleanup */" in css
    ux32 = css.split("/* UX-32 Task-first intro, booking flow V2, navigation cleanup */", 1)[1]
    assert "@media (max-width: 50rem)" in ux32
    assert ".home-primary-actions, .booking-path-switcher, .sigroom-howto-list { grid-template-columns: 1fr; }" in ux32

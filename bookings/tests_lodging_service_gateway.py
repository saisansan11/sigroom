from pathlib import Path

import pytest
from django.urls import reverse

from accounts.models import Unit, User
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "lodging" / "lodging_about.html"
CSS = ROOT / "static" / "css" / "lodging_about.css"
JS = ROOT / "static" / "js" / "lodging_about_explorer.js"


def _user(username, *, unit=None, superuser=False):
    return User.objects.create_user(
        username=username,
        email=f"{username}@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        is_superuser=superuser,
        is_staff=superuser,
    )


def _room(code, category, *, unit=None):
    room = Resource.objects.create(
        code=code,
        name=f"ห้อง {code}",
        building="อาคารทดสอบ Gateway",
        floor="1",
        resource_type=Resource.Type.ROOM,
        room_category=category,
        capacity=5,
        owner_unit=unit,
    )
    ResourceRule.objects.create(resource=room)
    return room


def test_public_page_is_service_gateway_with_three_clear_entries(client):
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")

    assert "SIGROOM Service Gateway" in html
    assert "จองห้องพัก" in html
    assert "จองห้องสอน" in html
    assert "ห้องเรียน / ประชุม" in html
    assert "กำลังพัฒนาระบบ" in html
    assert "งานห้องพัก" in html
    assert "บก.กศ.รร.ส.สส." in html
    assert "แผนกสนับสนุนการศึกษา" in html


def test_gateway_keeps_statistics_informational_and_3d_action_real(client):
    html = client.get(reverse("bookings:lodging_about")).content.decode("utf-8")
    assert 'class="lka-hero-chips lka-info-chips"' in html
    assert '>87<' in html
    assert '>234<' in html
    assert 'id="lka-hub-action-3d"' in html
    assert 'id="lka-explorer"' in html
    assert 'href="#lka-explorer"' in html
    assert 'id="lka-explorer-shell"' in html


def test_online_teaching_section_exposes_exact_three_signal_school_rooms(client):
    html = client.get(reverse("bookings:lodging_about")).content.decode("utf-8")
    for index in range(1, 4):
        assert f"ห้องสอนออนไลน์ {index}" in html
        assert f"STU-ONLINE-{index}" in html
    assert html.count("รองรับ 5 คน") == 3
    assert "กล้อง · ไมโครโฟน · ไฟสตูดิโอ · จอเขียว" in html


def test_gateway_icons_are_svg_components_and_template_has_no_emoji_clipart():
    source = TEMPLATE.read_text(encoding="utf-8")
    assert 'gateway_icon.html' in source
    assert not any(ord(char) >= 0x1F000 for char in source)
    assert "<svg" not in source  # icons are centralized in the reusable component
    component = (ROOT / "templates" / "lodging" / "partials" / "gateway_icon.html").read_text(encoding="utf-8")
    assert '<svg class="lka-icon' in component


def test_mobile_rates_have_data_labels_and_single_faq_indicator_contract():
    source = TEMPLATE.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert 'data-label="ปรับอากาศ · รายวัน"' in source
    assert 'data-label="พัดลม · รายเดือน"' in source
    assert "lka-faq-icon" not in source
    assert ".lka-faq-question::after" in css
    assert ".lka-rates-table td::before" in css


def test_zoning_filter_legend_and_future_area_are_present():
    source = TEMPLATE.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")
    for filter_name in ("all", "air", "fan", "facility", "future"):
        assert f'data-filter="{filter_name}"' in source
    for zone_class in ("zone-lodging", "zone-online", "zone-learning", "zone-service", "zone-future"):
        assert zone_class in source
    assert "408 · พื้นที่ไม่เปิดจอง" in js
    assert "409 · พื้นที่ไม่เปิดจอง" in js
    assert "410 · พื้นที่ไม่เปิดจอง" in js
    assert "filter === 'future'" in js


def test_reduced_transparency_and_minimum_body_size_contract():
    css = CSS.read_text(encoding="utf-8")
    assert "font-size: 16px" in css
    assert "@media (prefers-reduced-transparency: reduce)" in css
    assert "overflow-x: clip" in css


def test_staff_gateway_is_login_first(client):
    for service in ("lodging", "online", "learning"):
        response = client.get(reverse("bookings:service_staff_entry", args=[service]))
        assert response.status_code == 302
        assert reverse("login") in response.url


def test_staff_gateway_rejects_authenticated_user_without_owner_role(client):
    unit = Unit.objects.create(code="GW-NO", name="หน่วยทดสอบไม่มีสิทธิ์")
    user = _user("gateway-no-role", unit=unit)
    client.force_login(user)
    for service in ("lodging", "online", "learning"):
        assert client.get(reverse("bookings:service_staff_entry", args=[service])).status_code == 403


def test_online_custodian_is_redirected_to_usage_workspace(client):
    unit = Unit.objects.create(code="GW-ON", name="บก.กศ. ทดสอบ")
    staff = _user("gateway-online-staff", unit=unit)
    room = _room("GW-ONLINE", Resource.Category.ONLINE, unit=unit)
    room.custodians.add(staff)
    client.force_login(staff)

    response = client.get(reverse("bookings:service_staff_entry", args=["online"]))
    assert response.status_code == 302
    assert response.url == reverse("usage:list")


def test_learning_custodian_is_redirected_to_usage_workspace(client):
    unit = Unit.objects.create(code="GW-LEARN", name="สนับสนุนการศึกษา ทดสอบ")
    staff = _user("gateway-learning-staff", unit=unit)
    room = _room("GW-MEET", Resource.Category.MEETING, unit=unit)
    room.custodians.add(staff)
    client.force_login(staff)

    response = client.get(reverse("bookings:service_staff_entry", args=["learning"]))
    assert response.status_code == 302
    assert response.url == reverse("usage:list")


def test_staff_gateway_superuser_can_enter_all_operational_routes(client):
    admin = _user("gateway-admin", superuser=True)
    client.force_login(admin)
    lodging = client.get(reverse("bookings:service_staff_entry", args=["lodging"]))
    online = client.get(reverse("bookings:service_staff_entry", args=["online"]))
    learning = client.get(reverse("bookings:service_staff_entry", args=["learning"]))
    assert lodging.status_code == 302 and lodging.url == reverse("bookings:lodging_workspace")
    assert online.status_code == 302 and online.url == reverse("usage:list")
    assert learning.status_code == 302 and learning.url == reverse("usage:list")


def test_staff_gateway_unknown_service_is_404_after_login(client):
    admin = _user("gateway-admin-404", superuser=True)
    client.force_login(admin)
    response = client.get(reverse("bookings:service_staff_entry", args=["unknown"]))
    assert response.status_code == 404

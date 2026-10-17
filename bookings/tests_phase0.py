import re

import pytest
from django.urls import reverse

from accounts.models import Unit, User
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


def test_calendar_name_resolves_to_home_path():
    assert reverse("bookings:calendar") == "/home/"
    assert reverse("bookings:calendar_root") == "/"


def test_home_ok_for_anonymous_and_logged_in(client):
    assert client.get("/home/").status_code == 200
    unit = Unit.objects.create(code="P0", name="หน่วยทดสอบ")
    user = User.objects.create_user("phase0", "phase0@signalschool.ac.th", "Password-2569", unit=unit)
    client.force_login(user)
    assert client.get("/home/").status_code == 200


def test_root_still_serves_home_without_redirect(client):
    assert client.get("/").status_code == 200


def test_fullcalendar_scripts_are_deferred(client):
    html = client.get("/home/").content.decode("utf-8")
    tags = re.findall(r"<script[^>]*fullcalendar[^>]*>", html)
    assert len(tags) == 2
    assert all(" defer" in tag for tag in tags)


def test_thai_body_font_preload_present(client):
    html = client.get("/home/").content.decode("utf-8")
    assert re.search(r'<link rel="preload" as="font" type="font/woff2" crossorigin href="[^"]*sarabun-400-thai[^"]*\.woff2">', html)


def test_manifest_starts_at_home(client):
    assert '"start_url": "/home/"' in client.get("/manifest.webmanifest").content.decode("utf-8")


def test_home_is_service_gateway_with_collapsed_detail(client):
    response = client.get(reverse("bookings:calendar"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    for label in ("ห้องเรียน / ประชุม", "ห้องสอนออนไลน์", "ห้องพัก"):
        assert label in html
    assert 'class="home-service-gateway"' in html
    assert 'class="home-status-disclosure"' in html
    assert '<details class="home-status-disclosure" open' not in html
    assert "ดูสถานะห้องวันนี้" in html


def test_home_staff_gateway_only_shows_assigned_service(client):
    unit = Unit.objects.create(code="P0-STAFF", name="หน่วยทดสอบ staff gateway")
    staff = User.objects.create_user(
        "phase0-online-staff",
        "phase0-online-staff@signalschool.ac.th",
        "Password-2569",
        unit=unit,
    )
    online_room = Resource.objects.create(
        code="P0-ONLINE",
        name="ห้องออนไลน์ P0",
        owner_unit=unit,
        room_category=Resource.Category.ONLINE,
    )
    ResourceRule.objects.create(resource=online_room)
    online_room.custodians.add(staff)
    client.force_login(staff)

    html = client.get(reverse("bookings:calendar")).content.decode("utf-8")
    assert "งานที่ฉันดูแล" in html
    assert "ดูแลห้องสอนออนไลน์" in html
    assert "ดูแลห้องเรียน / ประชุม" not in html
    assert "งานห้องพัก" not in html
    assert f"{reverse('bookings:service_staff_entry', args=['online'])}" in html

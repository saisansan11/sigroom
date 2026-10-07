import re

import pytest
from django.urls import reverse

from accounts.models import Unit, User

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


def test_root_redirects_to_gateway():
    # A1 makes the Service Gateway the canonical entry point; /home/ remains the status dashboard.
    from django.urls import resolve

    match = resolve("/")
    assert match.url_name == "calendar_root"


def test_root_redirect_response_targets_gateway(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == "/lodging/about/"


def test_fullcalendar_scripts_are_deferred(client):
    index_html = client.get("/home/").content.decode("utf-8")
    assert not re.findall(r"<script[^>]*fullcalendar[^>]*>", index_html)

    html = client.get(reverse("bookings:room_status", args=["classroom"])).content.decode("utf-8")
    tags = re.findall(r"<script[^>]*fullcalendar[^>]*>", html)
    assert len(tags) == 2
    assert all(" defer" in tag for tag in tags)


def test_thai_body_font_preload_present(client):
    html = client.get("/home/").content.decode("utf-8")
    assert re.search(r'<link rel="preload" as="font" type="font/woff2" crossorigin href="[^"]*sarabun-400-thai[^"]*\.woff2">', html)


def test_manifest_starts_at_home(client):
    assert '"start_url": "/home/"' in client.get("/manifest.webmanifest").content.decode("utf-8")

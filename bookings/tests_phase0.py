"""ทดสอบ Phase 0 (แก้หน้าขาวตอนเปิดครั้งแรก): พาธ /home/ และสคริปต์ปฏิทินแบบ defer
รัน: uv run pytest bookings/tests_phase0.py
"""
import pytest
from django.urls import reverse

from accounts.models import Unit, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    unit = Unit.objects.create(code="COMM", name="แผนกวิชาการสื่อสาร")
    return User.objects.create_user(username="somchai", email="somchai@signalschool.ac.th", password="x" * 12, unit=unit)


def test_calendar_name_points_to_home_path():
    assert reverse("bookings:calendar") == "/home/"


def test_home_ok_for_anonymous(client):
    assert client.get("/home/").status_code == 200


def test_home_ok_for_logged_in(client, user):
    client.force_login(user)
    assert client.get("/home/").status_code == 200


def test_root_still_serves_calendar_for_lan_users(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "ปฏิทิน" in response.content.decode()


def test_calendar_scripts_are_deferred(client):
    html = client.get("/home/").content.decode()
    for name in ("index.global.min.js", "locales-all.global.min.js"):
        tags = [line for line in html.split("<script") if name in line]
        assert tags and all(t.lstrip().startswith("defer") for t in tags)


def test_base_preloads_thai_font(client):
    html = client.get("/home/").content.decode()
    assert 'rel="preload"' in html and "ibm-plex-sans-thai-400-thai.woff2" in html

from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_firebase_splash_targets_gateway_and_not_home():
    html = (Path(settings.BASE_DIR) / "public" / "index.html").read_text(encoding="utf-8")
    assert "location.replace('/lodging/about/'+location.search+location.hash)" in html
    assert "location.replace('/home/'" not in html
    assert 'href="/lodging/about/">เข้าสู่ SIGROOM' in html


def test_root_redirects_to_gateway_and_keeps_query_string(client):
    response = client.get(reverse("bookings:calendar_root") + "?source=school#ignored")
    assert response.status_code == 302
    assert response["Location"] == "/lodging/about/?source=school"


def test_home_status_page_still_exists(client):
    response = client.get(reverse("bookings:calendar"))
    assert response.status_code == 200

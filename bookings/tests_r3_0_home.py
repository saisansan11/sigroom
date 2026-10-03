from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_home_r3_0_is_category_index_not_combined_ledger(client):
    response = client.get(reverse("bookings:calendar"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'class="status-category-grid"' in html
    assert 'id="today-board"' not in html
    assert 'id="home-more"' not in html
    assert "ทุกหมวดห้อง" not in html


def test_room_status_ledger_has_no_room_thumbnail_markup():
    template = (Path(settings.BASE_DIR) / "templates" / "bookings" / "room_status.html").read_text(encoding="utf-8")
    ledger = template[template.index('<section id="today-board"'):template.index('<details id="home-more"')]
    assert "ledger-thumb" not in ledger
    assert "cover_photo" not in ledger


def test_room_status_uses_only_one_secondary_disclosure(client):
    response = client.get(reverse("bookings:room_status", args=["classroom"]))
    html = response.content.decode("utf-8")
    assert '<details id="home-more" class="home-more">' in html
    assert '<details id="operational-calendar-section"' not in html
    assert '<section id="operational-calendar-section"' in html
    assert 'href="#homepage-availability-section"' in html
    assert 'href="#operational-calendar-section"' in html


def test_home_r3_0_mobile_css_compacts_category_index():
    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert ".status-category-grid" in css
    assert "grid-template-columns: 1fr 1fr" in css
    assert ".home-more-summary { min-height: 44px;" in css

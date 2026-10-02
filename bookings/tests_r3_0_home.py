from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_home_r3_0_prioritizes_task_strip_then_today_ledger(client):
    response = client.get(reverse("bookings:calendar"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")

    assert 'id="today-board"' in html
    assert 'id="home-more"' in html
    assert html.index('id="today-board"') < html.index('id="home-more"')
    assert html.count('class="home-more-summary"') == 1
    assert ">ดูเพิ่มเติม<" in html


def test_home_r3_0_ledger_has_no_room_thumbnail_markup():
    template = (Path(settings.BASE_DIR) / "templates" / "bookings" / "calendar.html").read_text(encoding="utf-8")
    ledger = template[template.index('<section id="today-board"'):template.index('<details id="home-more"')]
    assert "ledger-thumb" not in ledger
    assert "cover_photo" not in ledger


def test_home_r3_0_uses_only_one_secondary_disclosure(client):
    response = client.get(reverse("bookings:calendar"))
    html = response.content.decode("utf-8")
    assert '<details id="home-more" class="home-more">' in html
    assert '<details id="operational-calendar-section"' not in html
    assert '<section id="operational-calendar-section"' in html
    assert 'href="#homepage-availability-section"' in html
    assert 'href="#operational-calendar-section"' in html


def test_home_r3_0_mobile_css_compacts_tasks_and_scrolls_category_filter():
    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert ".task-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }" in css
    assert ".task-cell-primary { grid-column: 1 / -1;" in css
    assert ".category-filter { flex-wrap: nowrap; overflow-x: auto;" in css
    assert ".home-more-summary { min-height: 44px;" in css

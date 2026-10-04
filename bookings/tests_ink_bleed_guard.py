from pathlib import Path

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from accounts.models import Unit, User
from bookings.online_teaching import ONLINE_TEACHER_GROUP

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_base_template_has_default_empty_body_attrs():
    base_html = _read("templates/base.html")
    assert '<body class="{% block body_class %}{% endblock %}"{% block body_attrs %}{% endblock %}>' in base_html


def test_enabled_surfaces_templates_include_data_ink_and_assets():
    lodging_about = _read("templates/lodging/lodging_about.html")
    online_home = _read("templates/bookings/online_teaching_home.html")
    online_book = _read("templates/bookings/online_teaching_book.html")

    for tpl in (lodging_about, online_home, online_book):
        assert '{% block body_attrs %} data-ink="on"{% endblock %}' in tpl
        assert "{% static 'css/ink_bleed.css' %}" in tpl
        assert "{% static 'js/ink_bleed.js' %}" in tpl


def test_staff_and_management_templates_never_load_ink_assets():
    excluded_templates = [
        "templates/lodging/dashboard.html",
        "templates/lodging/dashboard_room.html",
        "templates/lodging/workspace.html",
        "templates/lodging/manage_list.html",
        "templates/bookings/course_catalog_manage.html",
        "templates/bookings/calendar.html",
        "templates/reports/dashboard.html",
    ]

    for rel_path in excluded_templates:
        content = _read(rel_path)
        assert 'data-ink="on"' not in content, f"{rel_path} must not declare data-ink"
        assert "ink_bleed.css" not in content, f"{rel_path} must not load ink_bleed.css"
        assert "ink_bleed.js" not in content, f"{rel_path} must not load ink_bleed.js"


def test_lodging_about_rendered_page_has_ink_enabled(client):
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'data-ink="on"' in html
    assert "ink_bleed.css" in html
    assert "ink_bleed.js" in html


def test_calendar_rendered_page_excludes_ink(client):
    response = client.get(reverse("bookings:calendar"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'data-ink="on"' not in html
    assert "ink_bleed.css" not in html
    assert "ink_bleed.js" not in html


def test_online_teaching_home_rendered_page_has_ink_enabled(client):
    unit = Unit.objects.create(code="INK-EDU", name="กองการศึกษา")
    teacher = User.objects.create_user(
        username="ink-teacher",
        email="ink-teacher@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    group, _ = Group.objects.get_or_create(name=ONLINE_TEACHER_GROUP)
    teacher.groups.add(group)

    client.force_login(teacher)
    response = client.get(reverse("bookings:online_teaching_home"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'data-ink="on"' in html
    assert "ink_bleed.css" in html
    assert "ink_bleed.js" in html


def test_staff_dashboard_rendered_page_excludes_ink(client):
    unit = Unit.objects.create(code="INK-STAFF", name="แผนกสนับสนุนการศึกษา")
    staff = User.objects.create_user(
        username="ink-staff",
        email="ink-staff@signalschool.ac.th",
        password="Password-2569",
        is_staff=True,
        is_superuser=True,
        unit=unit,
    )

    client.force_login(staff)
    response = client.get(reverse("bookings:lodging_dashboard"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'data-ink="on"' not in html
    assert "ink_bleed.css" not in html
    assert "ink_bleed.js" not in html


def test_ink_bleed_css_contract():
    css = _read("static/css/ink_bleed.css")
    assert ".ink-bleed-canvas" in css
    assert "pointer-events: none" in css
    assert "mix-blend-mode: multiply" in css
    assert "prefers-reduced-motion: reduce" in css
    assert "opacity: 0.16" in css  # Must be <= 0.18 per contract
    # Theme color tokens for transient click rings
    for token in ("--ok", "--link", "--pending-text", "--stamp"):
        assert token in css, f"Theme token {token} must be defined for ink rings in ink_bleed.css"


def test_ink_bleed_js_contract():
    js = _read("static/js/ink_bleed.js")
    assert "var MAX_PARTICLES = 60;" in js
    assert "var MAX_ALPHA = 0.10;" in js
    assert "var MAX_DPR = 1.5;" in js
    assert "e.pointerType && e.pointerType !== 'mouse'" in js
    assert "prefers-reduced-motion: reduce" in js
    for token in ("--ok", "--link", "--pending-text", "--stamp"):
        assert token in js, f"Theme token {token} must be referenced in ink_bleed.js"

from pathlib import Path

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_base_template_has_default_empty_body_attrs():
    base_html = _read("templates/base.html")
    assert '<body class="{% block body_class %}{% endblock %}"{% block body_attrs %}{% endblock %}>' in base_html


def test_ink_assets_are_loaded_once_from_base_only():
    """ผู้ใช้ขอให้รอยสีน้ำตามเมาส์ทุกหน้า (5 ต.ค. 2569) จึงโหลดจาก base ที่เดียว"""
    base_html = _read("templates/base.html")
    assert base_html.count("{% static 'css/ink_bleed.css' %}") == 1
    assert base_html.count("{% static 'js/ink_bleed.js' %}") == 1
    for path in (ROOT / "templates").rglob("*.html"):
        if path.name == "base.html":
            continue
        assert "ink_bleed" not in path.read_text(encoding="utf-8"), f"{path} ต้องไม่โหลดหมึกซ้ำ"


def test_ink_script_respects_reduced_motion_and_page_opt_out():
    script = _read("static/js/ink_bleed.js")
    styles = _read("static/css/ink_bleed.css")
    assert "prefers-reduced-motion: reduce" in script
    assert "value !== 'off'" in script  # <body data-ink="off"> ปิดรายหน้า
    assert "preventDefault(" not in script  # ห้ามขวางการกดหรือหน่วงการนำทาง (มีแค่คำในคอมเมนต์)
    assert "pointer-events: none" in styles
    assert "@media (prefers-reduced-motion: reduce)" in styles


@pytest.mark.parametrize("url_name", ["bookings:lodging_about", "bookings:calendar", "bookings:lodging_start"])
def test_rendered_pages_load_ink_exactly_once(client, url_name):
    html = client.get(reverse(url_name)).content.decode("utf-8")
    assert html.count("ink_bleed.css") == 1
    assert html.count("ink_bleed.js") == 1

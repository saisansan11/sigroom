"""R3-G2 — /lodging/about/ เป็นหน้าเชิญชวน (Public Landing / Showcase) พร้อมโมเดลอาคาร 3 มิติ."""

import re
from pathlib import Path

import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

pytestmark = pytest.mark.django_db

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "lodging" / "lodging_about.html"
HERO_JS = ROOT / "static" / "js" / "lodging_about_hero3d.js"
HERO_CSS = ROOT / "static" / "css" / "lodging_about_r3g2.css"


def _html(client):
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200
    return response.content.decode("utf-8")


def _section(html, pattern):
    match = re.search(pattern, html, re.DOTALL)
    assert match is not None, pattern
    return match.group(0)


def test_hero_has_title_poster_stage_and_real_link_ctas(client):
    html = _html(client)
    hero = _section(html, r'<section class="lka-g2-hero".*?</section>')
    assert "<h1" in hero and ('alt="SIGROOM"' in hero.split("</h1>")[0])  # โลโก้เป็นเนื้อหาของ h1 (alt = ชื่อระบบ)
    assert "ที่พักและบริการห้องของโรงเรียนทหารสื่อสาร" in hero
    # 3D container + poster shown first (size reserved by width/height)
    assert 'id="lka-hero-stage"' in hero
    assert 'data-mode="poster"' in hero
    assert 'class="lka-hero-poster"' in hero
    assert 'width="1200" height="900"' in hero
    assert 'data-model-label="' in hero  # canvas aria-label source
    assert 'alt="ภาพจำลองสามมิติอาคารที่พักนักเรียน' in hero
    assert 'id="lka-hero-hint"' in hero
    # CTAs are real links
    assert '<a class="lka-g2-cta lka-g2-cta--primary" href="#lka-preview-hub">ดูห้องพัก</a>' in hero
    assert '<a class="lka-g2-cta lka-g2-cta--ghost" href="#lka-explorer">สำรวจแบบ 3 มิติ</a>' in hero
    assert 'id="lka-hero-toggle"' in hero and "หยุดหมุน" in hero


def test_hero_poster_assets_exist():
    for name in ("sigroom-building-640", "sigroom-building-1200"):
        for ext in ("webp", "avif"):
            assert finders.find(f"img/hero/{name}.{ext}"), f"{name}.{ext}"


def test_four_service_channels_with_correct_links(client):
    html = _html(client)
    services = _section(html, r'<section class="lka-section lka-g2-services" id="lka-preview-hub".*?</section>')
    assert "วันนี้ต้องการทำอะไร" in services
    for label, href in (
        ("จองห้องพัก", reverse("bookings:lodging_start")),
        ("จองห้องสอนออนไลน์", reverse("bookings:online_teaching_home")),
        ("จองห้องเรียน", reverse("bookings:book_search") + "?category=classroom"),
        ("จองห้องประชุม", reverse("bookings:book_search") + "?category=meeting"),
    ):
        assert label in services
        assert f'href="{href}"' in services
    assert services.count("lka-r3g-service ") >= 4
    lodging = _section(services, r'<a class="lka-r3g-service lka-r3g-service--lodging".*?</a>')
    assert lodging.count("<a ") == 1
    assert "นักเรียนหลักสูตรและข้าราชการทหาร" in lodging
    start_html = client.get(reverse("bookings:lodging_start")).content.decode()
    assert f'href="{reverse("bookings:lodging_index")}"' in start_html
    assert f'href="{reverse("bookings:lodging_general_request")}"' in start_html


def test_classroom_and_meeting_channels_are_clickable():
    source = TEMPLATE.read_text(encoding="utf-8")
    assert "กำลังพัฒนาระบบ" not in source
    assert "?category=classroom" in source
    assert "?category=meeting" in source


def test_page_order_hero_services_showcase_then_folded_info(client):
    html = _html(client)
    order = [
        'class="lka-g2-hero"',
        'id="lka-preview-hub"',
        'id="lka-gallery"',
        'id="lka-explorer"',
        'id="lka-online-rooms"',
        "lka-facilities-section",
        "lka-g2-info-heading",
        'id="lka-rates"',
        "lka-sitemap-disclosure",
        'id="lka-faq"',
        "lka-r3g-staff-line",
    ]
    positions = [html.index(marker) for marker in order]
    assert positions == sorted(positions)


def test_fees_faq_and_site_plan_are_inside_details(client):
    html = _html(client)
    rates = _section(html, r'<section class="lka-section lka-rates-section".*?</section>')
    assert re.search(r'<section[^>]*>\s*<details class="lka-disclosure lka-rates-disclosure">', rates)
    assert "<table" in rates.split("<details", 1)[1]
    faq = _section(html, r'<section class="lka-section lka-faq-section".*?</section>')
    assert re.search(r'<section[^>]*>\s*<details class="lka-disclosure lka-faq-disclosure">', faq)
    assert '<details class="lka-disclosure lka-sitemap-disclosure">' in html


def test_hero_script_is_page_local_self_hosted_and_guarded():
    source = TEMPLATE.read_text(encoding="utf-8")
    assert "js/lodging_about_hero3d.js' %}\" defer" in source
    js = HERO_JS.read_text(encoding="utf-8")
    for forbidden in ("http://", "https://", "import(", "cdn."):
        assert forbidden not in js
    # poster-first + fallbacks
    assert "requestIdleCallback" in js
    assert "IntersectionObserver" in js
    assert "prefers-reduced-motion: reduce" in js
    assert "hardwareConcurrency" in js and "deviceMemory" in js
    assert "getContext('webgl'" in js
    assert "webglcontextlost" in js
    assert "aria-label" in js
    # budget: hand-written renderer stays tiny
    assert HERO_JS.stat().st_size < 40_000


def test_hero_touch_does_not_trap_page_scroll():
    css = HERO_CSS.read_text(encoding="utf-8")
    assert "touch-action: pan-y" in css
    assert "aspect-ratio: 4 / 3" in css
    assert "focus-visible" in css

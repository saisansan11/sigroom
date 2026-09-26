"""
UX-20 Lodging About Immersive Stay Experience — contract tests.

Covers:
1. Public 200 access without authentication
2. New experience architecture sections in order:
   - Service Gateway hero with three service states, real room4p_3421 image, real-photo badge,
     informational lodging stats, and absence of old pseudo-3D hero cards
   - Service entries for lodging, online teaching, and classroom/meeting future state
   - Stay Photo Gallery (#lka-gallery) with featured real photos
   - Service Gateway (#lka-preview-hub) with real 3D/fallback actions and booking routes
   - Interactive Floor Explorer inside expandable details shell (#lka-explorer-shell) with all control IDs, canvas, and fallback
   - Online teaching rooms section with the three canonical Signal School rooms
   - Compact login-first staff entry and classroom/meeting future-state section
   - Facilities & Shared Spaces with disclosure class (.lka-facilities-disclosure), structured amenity cards, and 3 bath photos
   - Rates & Important Notes with disclosure class (.lka-rates-disclosure), summary cards, official table, rates announcement image,
     and floor overview cards with exact room counts and ranges
   - Site Map disclosure (.lka-sitemap-disclosure)
   - FAQ section (#lka-faq)
   - Final CTA section (.lka-cta) linking to lodging_index, lodging_general_request, and #lka-explorer
3. Disclaimers: Floor Explorer carries representational non-exact-model disclaimer ('ไม่ใช่แบบวัดขนาดจริง') without obsolete hero BIM copy
4. Performance & offline rules: no external CDNs, no remote 3D (Spline/Three.js), no WebGL
5. Lazy loading on non-hero imagery (at least 8 images)
6. Scoped CSS under .lka-* with reduced motion and overflow shield
7. JS floor switcher helper (lkaSwitchFloor)

Run with: uv run pytest bookings/tests_ux20_lodging_about.py -v
"""

from pathlib import Path
import pytest
from django.test import Client
from django.urls import reverse

from bookings.lodging_about_data import (
    ELECTRICITY_AIR_BAHT_PER_UNIT,
    ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH,
    FLOOR4_BED_COUNT,
    FLOOR4_ROOM_COUNT,
    FLOOR5_BED_COUNT,
    FLOOR5_ROOM_COUNT,
    MONTHLY_THRESHOLD_DAYS,
    RATES,
    TOTAL_BEDS,
    TOTAL_ROOMS,
)

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = WORKTREE_ROOT / "templates" / "lodging" / "lodging_about.html"
CSS_PATH = WORKTREE_ROOT / "static" / "css" / "lodging_about.css"
JS_PATH = WORKTREE_ROOT / "static" / "js" / "lodging_about_explorer.js"
STATIC_DIR = WORKTREE_ROOT / "static" / "img" / "showcase"

pytestmark = pytest.mark.django_db


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Public Access & Route
# ---------------------------------------------------------------------------

def test_ux20_lodging_about_public_access():
    """GET /lodging/about/ returns 200 without login redirect."""
    client = Client()
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"


# ---------------------------------------------------------------------------
# 2. Information Architecture & Key Sections in Rendered HTML
# ---------------------------------------------------------------------------

def test_ux20_hero_section_elements(client):
    """Hero is a Service Gateway with factual stats, service CTAs, and a real photo."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "lka-hero" in html, "Missing hero section"
    assert "จองพื้นที่ของโรงเรียน" in html, "Missing Service Gateway hero headline"
    assert "จากจุดเดียวใน SIGROOM" in html, "Missing Service Gateway hero emphasis"
    assert "lka-hero-chips lka-info-chips" in html, "Missing informational hero stats"
    assert str(TOTAL_ROOMS) in html, "Missing 87-room lodging statistic"
    assert str(TOTAL_BEDS) in html, "Missing 234-bed lodging statistic"
    assert "ชั้น 4–5" in html, "Missing lodging floor statistic"
    assert "lka-hero-photo-card" in html, "Missing real photo card in hero"
    assert "room4p_3421.jpg" in html, "Missing room4p_3421.jpg in hero"
    assert "ภาพถ่ายสถานที่จริง" in html, "Missing real photo badge"
    assert "จองห้องพัก" in html, "Missing lodging CTA"
    assert "จองห้องสอน" in html, "Missing online teaching CTA"
    assert "ห้องเรียน / ประชุม" in html, "Missing classroom/meeting service state"
    assert "กำลังพัฒนาระบบ" in html, "Missing classroom/meeting future state"
    assert "ดูแผนผัง 3D" in html, "Missing 3D plan action"

    # Explicitly assert old pseudo-3D hero classes are absent
    assert "lka-hero-card-3d" not in html, "Old pseudo-3D card class should be absent"
    assert "lka-iso-dorm-mockup" not in html, "Old pseudo-3D mockup class should be absent"
    assert "lka-hero-support-3d" not in html, "Old hero supportive 3D container should be absent"

def test_ux20_explorer_non_exact_model_disclaimer(client):
    """Floor Explorer contains non-exact-model representational disclaimer without obsolete BIM copy."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")
    assert "ไม่ใช่แบบวัดขนาดจริง" in html, (
        "Must clarify explorer diagram is representational and not exact dimensions"
    )
    assert "ไม่ใช่แบบสถาปัตยกรรม BIM" not in html, (
        "Old BIM copy should be removed from hero and template"
    )


def test_ux20_quick_highlights_section(client):
    """Former highlights are replaced by non-clickable facts inside the Service Gateway hero."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "lka-highlights-section" not in html, "Legacy highlights section should be removed"
    assert "lka-info-chips" in html, "Missing compact informational facts"
    assert str(TOTAL_ROOMS) in html, "Missing 87 total rooms"
    assert str(TOTAL_BEDS) in html, "Missing 234 total beds"
    assert "pointer-events: none" in _read_file(CSS_PATH), "Hero statistics should not behave like buttons"

def test_ux20_stay_gallery_section(client):
    """Gallery section contains featured and supporting real photos."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert 'id="lka-gallery"' in html, "Missing #lka-gallery anchor"
    assert "lka-gallery-section" in html, "Missing gallery section"
    assert "room4p_3421.jpg" in html, "Missing room4p_3421.jpg"
    assert "room2p_444.jpg" in html, "Missing room2p_444.jpg"
    assert "room2p_222.jpg" in html, "Missing room2p_222.jpg"
    assert "room4p_4444.jpg" in html, "Missing room4p_4444.jpg"


def test_ux20_preview_hub_and_action_ids(client):
    """Service Gateway exposes real lodging, online-teaching, 3D, and fallback routes."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert 'id="lka-preview-hub"' in html, "Missing #lka-preview-hub section"
    assert 'id="lka-hub-action-3d"' in html, "Missing #lka-hub-action-3d"
    assert 'id="lka-hub-action-fallback"' in html, "Missing #lka-hub-action-fallback"
    assert 'href="#lka-explorer"' in html, "Missing link to explorer"
    assert reverse("bookings:lodging_index") in html, "Missing link to lodging booking"
    assert reverse("bookings:online_teaching_home") in html, "Missing link to online-teaching booking"
    assert 'href="#lka-explorer-fallback"' in html, "Missing link to fallback plan"
    assert "กำลังพัฒนาระบบ" in html, "Missing non-bookable classroom/meeting state"

def test_ux20_explorer_shell_details(client):
    """Interactive Floor Explorer uses expandable details shell architecture."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert 'id="lka-explorer"' in html, "Missing #lka-explorer anchor"
    assert 'id="lka-explorer-shell"' in html, "Missing #lka-explorer-shell details"
    assert "lka-explorer-shell" in html, "Missing lka-explorer-shell class"
    assert "lka-explorer-shell-trigger" in html, "Missing lka-explorer-shell-trigger summary"
    assert "lka-explorer-shell-body" in html, "Missing lka-explorer-shell-body container"

    # Old room experience section class must be absent
    assert "lka-experience-section" not in html, "Old room experience section should be removed"


def test_ux20_interactive_explorer_hooks_intact(client):
    """Explorer maintains all critical DOM IDs, ARIA semantics, and control attributes."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert 'id="lka-explorer"' in html, "Missing #lka-explorer anchor"
    assert 'id="lka-btn-f4"' in html, "Missing Floor 4 toggle button"
    assert 'id="lka-btn-f5"' in html, "Missing Floor 5 toggle button"
    assert 'data-floor="4"' in html, "Missing data-floor=4"
    assert 'data-floor="5"' in html, "Missing data-floor=5"

    assert 'data-filter="all"' in html, "Missing all filter"
    assert 'data-filter="air"' in html, "Missing air filter"
    assert 'data-filter="fan"' in html, "Missing fan filter"
    assert 'data-filter="facility"' in html, "Missing facility filter"

    assert 'id="lka-explorer-canvas"' in html, "Missing canvas container"
    assert 'id="lka-iso-scene"' in html, "Missing iso scene container"
    assert 'id="lka-room-picker"' in html, "Missing room picker"
    assert 'id="lka-perspective"' in html, "Missing perspective button"
    assert 'id="lka-zoom-in"' in html, "Missing zoom in"
    assert 'id="lka-zoom-out"' in html, "Missing zoom out"
    assert 'id="lka-reset"' in html, "Missing reset button"
    assert 'id="lka-room-panel"' in html, "Missing room detail panel"
    assert 'id="lka-panel-close"' in html, "Missing panel close button"
    assert 'id="lka-explorer-fallback"' in html, "Missing accessible fallback"


def test_ux20_floor_overview_cards_and_exact_ranges(client):
    """Floor overview diagrams and cards preserve room counts and exact room number ranges."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "floor4.png" in html, "Missing floor4.png diagram"
    assert "floor5.png" in html, "Missing floor5.png diagram"

    # Floor 4 facts
    assert str(FLOOR4_ROOM_COUNT) in html, "Missing Floor 4 room count (57)"
    assert str(FLOOR4_BED_COUNT) in html, "Missing Floor 4 bed count (114)"
    assert "401–407" in html or "401-407" in html, "Missing Floor 4 air room range"
    assert "417–448" in html or "417-448" in html, "Missing Floor 4 fan room range"

    # Floor 5 facts
    assert str(FLOOR5_ROOM_COUNT) in html, "Missing Floor 5 room count (30)"
    assert str(FLOOR5_BED_COUNT) in html, "Missing Floor 5 bed count (120)"
    assert "501–530" in html or "501-530" in html, "Missing Floor 5 air room range"


def test_ux20_floor_overview_floor_switching_attributes(client):
    """Floor overview cards have semantic data-explorer-floor targets and valid href fallback."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    # Floor 4 card button
    assert 'data-explorer-floor="4"' in html, "Missing data-explorer-floor=4 on Floor 4 card"
    # Floor 5 card button
    assert 'data-explorer-floor="5"' in html, "Missing data-explorer-floor=5 on Floor 5 card"
    # Both preserve href="#lka-explorer" for progressive enhancement
    assert 'href="#lka-explorer"' in html


def test_ux20_journey_and_why_sections(client):
    """Legacy journey/why blocks are replaced by operational service information."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "lka-journey-section" not in html, "Legacy journey section should be removed"
    assert "lka-why-section" not in html, "Legacy why-SIGROOM section should be removed"
    assert "ทำไมต้อง SIGROOM" not in html, "Legacy why-SIGROOM copy should be removed"

    assert 'id="lka-online-rooms"' in html, "Missing online teaching rooms section"
    for index in range(1, 4):
        assert f"ห้องสอนออนไลน์ {index}" in html
        assert f"STU-ONLINE-{index}" in html
    assert "สำหรับครูและอาจารย์" in html
    assert "บก.กศ.รร.ส.สส." in html
    assert "งานห้องพัก" in html
    assert "แผนกสนับสนุนการศึกษา" in html
    assert "ทางเข้าจัดการงาน" in html

def test_ux20_disclosure_classes(client):
    """Facilities, Rates, and Site Map sections use semantic disclosure classes."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "lka-facilities-disclosure" in html, "Missing lka-facilities-disclosure class"
    assert "lka-rates-disclosure" in html, "Missing lka-rates-disclosure class"
    assert "lka-sitemap-disclosure" in html, "Missing lka-sitemap-disclosure class"


def test_ux20_facilities_cards_and_photos(client):
    """Facilities section displays structured amenity cards and 3 bathroom photos."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "lka-facilities-section" in html, "Missing facilities section"
    assert "ห้องน้ำส่วนกลาง" in html, "Missing bathrooms title"
    assert "ห้องอาบน้ำส่วนกลาง" in html, "Missing showers title"
    assert "โถปัสสาวะ 10, ห้องสุขา 10" in html, "Missing bathroom fixture details"
    assert "ฝั่งละ 20 ห้อง" in html, "Missing shower count details"
    assert "bath1.jpg" in html, "Missing bath1.jpg"
    assert "bath2.jpg" in html, "Missing bath2.jpg"
    assert "bath3.jpg" in html, "Missing bath3.jpg"


def test_ux20_lodging_about_view_context(client):
    """View passes authoritative constants from lodging_about_data.py in context."""
    response = client.get(reverse("bookings:lodging_about"))
    assert response.context["rates"] == RATES
    assert response.context["electricity_air_baht_per_unit"] == ELECTRICITY_AIR_BAHT_PER_UNIT
    assert response.context["electricity_fan_flat_baht_per_month"] == ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH
    assert response.context["monthly_threshold_days"] == MONTHLY_THRESHOLD_DAYS


def test_ux20_rates_no_hardcoded_literals_in_template():
    """Template must use context variables rather than hardcoded rate constants."""
    tmpl = _read_file(TEMPLATE_PATH)
    # Check that context variables are used in the template
    assert "{{ electricity_air_baht_per_unit }}" in tmpl
    assert "{{ electricity_fan_flat_baht_per_month }}" in tmpl
    assert "{{ monthly_threshold_days }}" in tmpl
    # Check that hardcoded literals in rates section have been removed
    assert "หน่วยละ <strong>5 บาท</strong>" not in tmpl
    assert "<strong>200 บาท/เดือน</strong>" not in tmpl
    assert "<strong>20 วัน</strong>" not in tmpl


def test_ux20_rates_rendered_from_authoritative_constants(client):
    """Rendered HTML displays rate constants matching source of truth across all sections."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    # Rates subtitle
    assert f"พักตั้งแต่ {MONTHLY_THRESHOLD_DAYS} วันขึ้นไปนับเป็น 1 เดือน" in html
    # Summary cards
    assert f"หน่วยละ <strong>{ELECTRICITY_AIR_BAHT_PER_UNIT} บาท</strong>" in html
    assert f"เหมาจ่ายค่าไฟฟ้า <strong>{ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH} บาท/เดือน</strong>" in html
    assert f"พักตั้งแต่ <strong>{MONTHLY_THRESHOLD_DAYS} วัน</strong> ขึ้นไป นับเป็น 1 เดือน" in html
    # Notes list
    assert f"ห้องปรับอากาศ: คิดตามมิเตอร์ หน่วยละ <strong>{ELECTRICITY_AIR_BAHT_PER_UNIT} บาท</strong>" in html
    assert f"ห้องพัดลม: เหมาจ่าย <strong>{ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH} บาท/เดือน</strong>" in html
    assert f"พัก {MONTHLY_THRESHOLD_DAYS} วันขึ้นไป นับเป็น 1 เดือน" in html


def test_ux20_rates_section_structure(client):
    """Rates section has summary cards, full table with all categories, and rates.png."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert 'id="lka-rates"' in html, "Missing #lka-rates section"
    assert "lka-rates-summary-grid" in html, "Missing rates summary grid"
    assert f"{ELECTRICITY_AIR_BAHT_PER_UNIT} บาท" in html
    assert f"{ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH}" in html
    assert f"{MONTHLY_THRESHOLD_DAYS} วัน" in html

    for rate in RATES:
        assert rate["category"] in html, f"Missing rate category {rate['category']}"

    assert "rates.png" in html, "Missing official rates announcement image"


def test_ux20_faq_section(client):
    """FAQ section answers common questions regarding stay and booking."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert 'id="lka-faq"' in html, "Missing #lka-faq anchor"
    assert "lka-faq-section" in html, "Missing FAQ section"
    assert "lka-faq-item" in html, "Missing FAQ items"
    assert "คำถามที่พบบ่อย" in html, "Missing FAQ title"


def test_ux20_final_cta_links(client):
    """Final CTA section links to lodging index, general request, and top explorer."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "lka-cta" in html, "Missing final CTA section"
    assert 'id="lka-cta-heading"' in html, "Missing CTA heading ID"
    lodging_url = reverse("bookings:lodging_index")
    assert lodging_url in html, f"CTA must link to {lodging_url}"
    general_url = reverse("bookings:lodging_general_request")
    assert general_url in html, f"CTA must link to {general_url}"
    assert 'href="#lka-explorer"' in html, "CTA must allow returning to explorer"


# ---------------------------------------------------------------------------
# 3. Performance, Security & Asset Hygiene
# ---------------------------------------------------------------------------

def test_ux20_no_remote_cdn_or_3d_engine():
    """Template must have no external CDNs, Spline, Three.js, or WebGL renderer."""
    html = _read_file(TEMPLATE_PATH)
    js = _read_file(JS_PATH)

    for forbidden in ["cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com", "three.js", "spline", "sketchfab"]:
        assert forbidden not in html.lower(), f"Forbidden external dependency in template: {forbidden}"
        assert forbidden not in js.lower(), f"Forbidden external dependency in JS: {forbidden}"


def test_ux20_lazy_loading_image_count():
    """At least 8 below-the-fold showcase images must have loading='lazy'."""
    html = _read_file(TEMPLATE_PATH)
    lazy_count = html.count('loading="lazy"')
    assert lazy_count >= 8, f"Expected at least 8 lazy loaded images, got {lazy_count}"


def test_ux20_css_rules_and_reduced_motion():
    """CSS must define scoped styles, overflow shield, and prefers-reduced-motion."""
    css = _read_file(CSS_PATH)
    assert ".lka-hero" in css, "Missing .lka-hero in CSS"
    assert "overflow-x: clip" in css or "overflow: hidden" in css, "Missing overflow protection in CSS"
    assert "@media (prefers-reduced-motion: reduce)" in css, "Missing reduced-motion media query"


def test_ux20_js_floor_switch_helper_and_wiring():
    """JS must expose window.lkaSwitchFloor helper function and wire data-explorer-floor clicks."""
    js = _read_file(JS_PATH)
    assert "window.lkaSwitchFloor = switchFloor;" in js, "Missing lkaSwitchFloor helper in JS"
    assert "data-explorer-floor" in js, "Missing querySelectorAll for data-explorer-floor in JS"
    assert "switchFloor(targetFloor)" in js or "switchFloor(btn.dataset.explorerFloor)" in js or "targetFloor" in js, (
        "Missing switchFloor call on data-explorer-floor click"
    )

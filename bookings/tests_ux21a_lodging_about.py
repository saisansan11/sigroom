"""
UX-21A Lodging About Bright Hospitality Re-direction — contract tests.

Validates:
1. Public 200 access without authentication.
2. Bright hospitality visual architecture:
   - Hero features real photo card showcase (room4p_3421.jpg) as the primary star.
   - Real photo badge ("ภาพถ่ายสถานที่จริง") and floating hospitality chips.
   - Elimination of old pseudo-3D hero cards/mockups and obsolete BIM disclaimers.
   - 3D launcher hub (#lka-preview-hub, #lka-hub-action-3d) and expandable explorer shell (#lka-explorer-shell).
3. Bright hospitality design tokens present in lodging_about.css:
   - Light canvas (--lka-canvas), white surfaces (--lka-surface).
   - Deep navy / slate typography (--lka-navy-900, --lka-navy-800).
   - Sky blue (--lka-sky), fresh mint (--lka-mint), warm sand/amber (--lka-amber).
   - Elimination of dark tech grid patterns and dark-tech background overlays.
4. Preservation of all Floor Explorer hooks, controls, and filters.
5. Strict performance and asset hygiene: local static assets only, overflow shield, reduced motion.

Run with: uv run pytest bookings/tests_ux21a_lodging_about.py -v
"""

from pathlib import Path
import pytest
from django.test import Client
from django.urls import reverse

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = WORKTREE_ROOT / "templates" / "lodging" / "lodging_about.html"
CSS_PATH = WORKTREE_ROOT / "static" / "css" / "lodging_about.css"
JS_PATH = WORKTREE_ROOT / "static" / "js" / "lodging_about_explorer.js"
UX27_CSS_PATH = WORKTREE_ROOT / "static" / "css" / "lodging_about_ux27.css"

pytestmark = pytest.mark.django_db


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ux21a_public_access_200():
    """GET /lodging/about/ returns 200 without login redirect."""
    client = Client()
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200


def test_ux21a_hero_real_photo_card(client):
    """Hero visual prominently features real room photography card without dark/tech overlay."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "lka-hero-photo-card" in html, "Missing real photo card in hero"
    assert "room4p_3421.jpg" in html, "Missing room4p_3421.jpg in hero photo frame"
    assert "lka-hero-main-img" in html, "Missing main hero image class"
    assert "ภาพถ่ายสถานที่จริง" in html, "Missing real photo badge"
    assert "lka-hero-chips" in html, "Missing floating chips in hero"


def test_ux21a_no_pseudo_3d_hero_mockup(client):
    """Hero has eliminated pseudo-3D building card and obsolete BIM disclaimer."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "lka-hero-card-3d" not in html, "Old pseudo-3D card class should be absent"
    assert "lka-hero-support-3d" not in html, "Old hero supportive 3D container should be absent"
    assert "lka-iso-dorm-mockup" not in html, "Old pseudo-3D mockup class should be absent"
    assert "ไม่ใช่แบบสถาปัตยกรรม BIM" not in html, "Old BIM copy should be absent"


def test_ux21a_3d_launcher_and_shell(client):
    """3D experience is organized as launcher hub and expandable explorer shell."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert 'id="lka-preview-hub"' in html, "Missing 3D preview hub"
    assert 'id="lka-hub-action-3d"' in html, "Missing 3D hub launcher action"
    assert 'id="lka-explorer-shell"' in html, "Missing expandable explorer shell"
    assert "lka-explorer-shell" in html, "Missing explorer shell class"
    assert "ไม่ใช่แบบวัดขนาดจริง" in html, "Missing non-exact-model explorer disclaimer"


def test_ux21a_bright_hospitality_tokens_in_css():
    """CSS defines bright hospitality tokens and eliminates dark cyber grid."""
    css = _read_file(CSS_PATH)

    # Required bright tokens
    assert "--lka-canvas: #f8fafc" in css, "Missing bright canvas token"
    assert "--lka-surface: #ffffff" in css, "Missing white surface token"
    assert "--lka-sky: #0369a1" in css, "Missing accessible sky blue accent"
    assert "--lka-mint: #0f766e" in css, "Missing accessible mint accent"
    assert "--lka-amber: #b45309" in css, "Missing accessible warm amber accent"
    assert "--lka-navy-900: #0f172a" in css, "Missing deep navy heading token"

    # Dark cyber grid must be removed
    assert "background-size: 32px 32px" not in css, "Dark tech 32px grid pattern must be eliminated"


def test_ux21a_overflow_and_accessibility_in_css():
    """CSS retains overflow protection, reduced motion query, and high-contrast typography."""
    css = _read_file(CSS_PATH)
    assert "overflow-x: clip" in css or "overflow: hidden" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert ".lka-page-wrap h1" in css or ".lka-page-wrap h2" in css


def test_ux21a_interactive_explorer_hooks_preserved(client):
    """Floor Explorer DOM hooks, IDs, and filters remain 100% operational."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert 'id="lka-explorer"' in html
    assert 'id="lka-btn-f4"' in html
    assert 'id="lka-btn-f5"' in html
    assert 'data-filter="all"' in html
    assert 'data-filter="air"' in html
    assert 'data-filter="fan"' in html
    assert 'data-filter="facility"' in html
    assert 'id="lka-explorer-canvas"' in html
    assert 'id="lka-iso-scene"' in html
    assert 'id="lka-room-panel"' in html
    assert 'id="lka-panel-close"' in html
    assert 'id="lka-room-picker"' in html
    assert 'id="lka-perspective"' in html
    assert 'id="lka-explorer-fallback"' in html


def test_ios27_lodging_theme_is_scoped_to_about_page(client):
    html = client.get(reverse("bookings:lodging_about")).content.decode("utf-8")
    assert '<html lang="th" data-theme="light">' in html
    assert '<body class="lodging-about-ios27">' in html
    assert '<meta name="theme-color" content="#f6f7fb">' in html


def test_ios27_visual_system_tokens_and_header_convergence():
    css = _read_file(CSS_PATH)
    assert "iOS 27-inspired unified lodging surface" in css
    assert "body.lodging-about-ios27 .site-header" in css
    assert "backdrop-filter: saturate(1.35) blur(24px)" in css
    assert "body.lodging-about-ios27 .mobile-menu-panel" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in css


def test_mobile_explorer_uses_true_fit_instead_of_fixed_760px_scene():
    css = _read_file(UX27_CSS_PATH)
    assert "min-width: 760px" not in css
    assert ".lka-explorer-section .lka-iso-scene" in css
    assert "min-width: 0" in css
    assert "max-width: 100%" in css
    assert "overscroll-behavior: contain" in css


def test_fit_control_resets_camera_and_scale():
    js = _read_file(JS_PATH)
    assert "function resetViewToFit()" in js
    assert "perspective = false;" in js
    assert "viewQuarter = 0;" in js
    assert "scale = 1;" in js
    assert "resetBtn.addEventListener('click', resetViewToFit)" in js

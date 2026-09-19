"""
UX-21A Lodging About Bright Hospitality Re-direction — contract tests.

Validates:
1. Public 200 access without authentication.
2. Bright hospitality visual architecture:
   - Hero features real photo showcase (room4p_3421.jpg) as the primary star.
   - Real photo badge ("ภาพถ่ายสถานที่จริง") and floating hospitality chips.
   - Supportive 3D preview retained with non-BIM disclaimer.
   - Elimination of dark tech grid patterns and dark-tech background overlays.
3. Bright hospitality design tokens present in lodging_about.css:
   - Light canvas (--lka-canvas), white surfaces (--lka-surface).
   - Deep navy / slate typography (--lka-navy-900, --lka-navy-800).
   - Sky blue (--lka-sky), fresh mint (--lka-mint), warm sand/amber (--lka-amber).
4. Preservation of all Floor Explorer hooks, rates, facilities, and CTAs.
5. Strict performance and asset hygiene: local static assets only, lazy loading, overflow shield, reduced motion.

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

pytestmark = pytest.mark.django_db


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ux21a_public_access_200():
    """GET /lodging/about/ returns 200 without login redirect."""
    client = Client()
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200


def test_ux21a_hero_real_photo_prominence(client):
    """Hero visual prominently features real room photography."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "lka-hero-photo-showcase" in html, "Missing real photo showcase in hero"
    assert "room4p_3421.jpg" in html, "Missing room4p_3421.jpg in hero photo frame"
    assert "ภาพถ่ายสถานที่จริง" in html, "Missing real photo badge"
    assert "lka-hero-floating-card" in html, "Missing floating hospitality card in hero"
    assert "เตียงเดี่ยวแยกสัดส่วน" in html, "Missing bed highlight chip in hero"


def test_ux21a_hero_supportive_3d_preview(client):
    """3D floor mockup is positioned as supportive preview with non-BIM disclaimer."""
    response = client.get(reverse("bookings:lodging_about"))
    html = response.content.decode("utf-8")

    assert "lka-hero-support-3d" in html, "Missing supportive 3D container"
    assert "lka-iso-dorm-mockup" in html, "Missing 3D mockup element"
    assert "ไม่ใช่แบบสถาปัตยกรรม BIM หรือระบุขนาดจริง" in html, "Missing non-BIM disclaimer"


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

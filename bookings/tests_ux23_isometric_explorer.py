"""UX-23 Lodging Isometric Explorer contract tests."""

from pathlib import Path

import pytest
from django.urls import reverse


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "lodging" / "lodging_about.html"
CSS = ROOT / "static" / "css" / "lodging_about_ux23.css"
JS = ROOT / "static" / "js" / "lodging_about_explorer.js"

pytestmark = pytest.mark.django_db


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_page_still_renders(client):
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200


def test_explorer_uses_architectural_view_controls():
    html = _read(TEMPLATE)
    assert 'id="lka-view-left"' in html
    assert 'id="lka-view-right"' in html
    assert 'id="lka-model-floor"' in html
    assert 'id="lka-model-view"' in html
    assert 'role="region"' in html


def test_explorer_hint_describes_plan_selection_and_optional_perspective():
    html = _read(TEMPLATE)
    # UX-27 intentionally starts overhead; touch scrolling must not rotate it.
    assert "แตะห้องเพื่อยกขึ้นดูข้อมูล" in html
    assert "มือถือเลื่อนผังซ้าย–ขวาได้" in html
    assert 'id="lka-perspective" aria-pressed="false"' in html


def test_js_builds_real_isometric_cuboid_faces():
    js = _read(JS)
    assert "cuboidFaces" in js
    assert "lka-room-face--x" in js
    assert "lka-room-face--y" in js
    assert "lka-room-model" in js
    assert "lka-building-base" in js
    assert "lka-corridor-model" in js
    assert "lka-facility-model" in js


def test_js_does_not_css_rotate_flat_scene_anymore():
    js = _read(JS)
    assert "rotateX(" not in js
    assert "rotateZ(" not in js
    assert "scene.style.transform = `scale(${scale})`" in js
    assert "viewQuarter" in js
    assert "orientPoint" in js


def test_js_preserves_room_truth_and_interactions():
    js = _read(JS)
    assert "401" in js and "460" in js
    assert "501" in js and "530" in js
    assert "showPanel" in js
    assert "applyFilter" in js
    assert "switchFloor" in js
    assert "ArrowLeft" in js and "ArrowRight" in js
    assert "touchstart" in js and "touchmove" in js


def test_css_has_3d_face_palette_and_selected_lift():
    css = _read(CSS)
    assert ".lka-room-model" in css
    assert ".lka-room-face--x" in css
    assert ".lka-room-face--y" in css
    assert ".lka-room-model.selected" in css
    assert ".lka-base-top" in css
    assert ".lka-corridor-top" in css


def test_no_remote_3d_engine_or_continuous_loop():
    js = _read(JS).lower()
    html = _read(TEMPLATE).lower()
    for forbidden in ("three.js", "webglrenderer", "spline", "sketchfab", "cdn.jsdelivr", "unpkg.com"):
        assert forbidden not in js
        assert forbidden not in html
    assert "setinterval" not in js
    assert "autorepeat" not in js

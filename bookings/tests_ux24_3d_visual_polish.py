"""UX-24 3D visual polish contract tests."""

from pathlib import Path

import pytest
from django.urls import reverse


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "lodging" / "lodging_about.html"
CSS = ROOT / "static" / "css" / "lodging_about_ux24.css"
JS = ROOT / "static" / "js" / "lodging_about_explorer.js"

pytestmark = pytest.mark.django_db


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_public_page_still_renders_with_ux24_stylesheet(client):
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "css/lodging_about_ux24.css" in html


def test_explorer_has_contextual_inspector_and_help_contract():
    html = _read(TEMPLATE)
    assert 'class="lka-explorer-layout"' in html
    assert 'data-state="empty"' in html
    assert 'class="lka-panel-empty"' in html
    assert 'class="lka-panel-content"' in html
    assert 'id="lka-model-selection"' in html
    assert 'id="lka-explorer-help"' in html
    assert 'aria-describedby="lka-explorer-help lka-explorer-fallback"' in html


def test_visual_polish_uses_shared_gradients_and_single_stage_shadow():
    js = _read(JS)
    css = _read(CSS)
    assert "appendModelDefs" in js
    assert "appendLinearGradient" in js
    assert "lka-air-top" in js
    assert "lka-fan-top" in js
    assert "lka-facility-top" in js
    assert "fill: url(#lka-air-top)" in css
    assert ".lka-iso-svg" in css
    assert ".lka-model-ground-shadow" in css


def test_selection_is_semantic_contextual_and_persists_across_camera_changes():
    js = _read(JS)
    assert "selectedRoomNumber" in js
    assert "'aria-pressed': isSelected ? 'true' : 'false'" in js
    assert "panel.dataset.state = 'selected'" in js
    assert "scene.classList.add('has-selection')" in js
    rotate_body = js.split("function rotateView(delta)", 1)[1].split("}", 1)[0]
    assert "closePanel()" not in rotate_body
    reset_body = js.split("if (resetBtn)", 1)[1].split("}", 2)[1]
    assert "closePanel()" not in reset_body


def test_plain_wheel_scrolling_is_not_trapped_by_canvas():
    js = _read(JS)
    wheel_body = js.split("canvas.addEventListener('wheel'", 1)[1]
    assert "if (!event.ctrlKey && !event.metaKey) return;" in wheel_body
    assert "event.preventDefault();" in wheel_body


def test_mobile_controls_and_inspector_have_explicit_touch_contract():
    css = _read(CSS)
    assert "min-height: 44px" in css
    assert "min-width: 44px" in css
    assert "@media (max-width: 720px)" in css
    assert "position: fixed" in css
    assert ".lka-room-panel.has-selection" in css


def test_no_heavy_remote_or_continuous_rendering_regression():
    source = (_read(JS) + _read(TEMPLATE) + _read(CSS)).lower()
    for forbidden in (
        "three.js",
        "webglrenderer",
        "spline",
        "sketchfab",
        "cdn.jsdelivr",
        "unpkg.com",
        "setinterval",
    ):
        assert forbidden not in source

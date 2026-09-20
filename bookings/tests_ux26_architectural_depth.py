"""UX-26 architectural depth contract tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "js" / "lodging_about_explorer.js"
CSS = ROOT / "static" / "css" / "lodging_about_ux24.css"
TEMPLATE = ROOT / "templates" / "lodging" / "lodging_about.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_model_adds_building_scale_architectural_cues():
    js = _read(JS)
    for marker in (
        "appendPerimeterWalls",
        "appendCirculationSpine",
        "lka-building-perimeter",
        "lka-circulation-spine",
        "lka-core-model",
    ):
        assert marker in js


def test_rooms_add_noninteractive_door_and_window_details():
    js = _read(JS)
    assert "appendRoomArchitecture" in js
    assert "lka-room-window" in js
    assert "lka-room-door" in js
    architecture = js.split("function appendRoomArchitecture", 1)[1].split("function makeSVG", 1)[0]
    assert "tabindex" not in architecture
    assert "role: 'button'" not in architecture
    assert "'aria-hidden': 'true'" in architecture


def test_architectural_details_have_visual_depth_styles():
    css = _read(CSS)
    for selector in (
        ".lka-building-perimeter",
        ".lka-circulation-spine",
        ".lka-core-model",
        ".lka-room-window",
        ".lka-room-door",
    ):
        assert selector in css


def test_lightweight_svg_contract_remains():
    source = (_read(JS) + _read(CSS)).lower()
    for forbidden in ("three.js", "webglrenderer", "setinterval", "cdn.jsdelivr", "unpkg.com"):
        assert forbidden not in source


def test_reduced_motion_and_text_fallback_contracts_remain():
    css = _read(CSS)
    html = _read(TEMPLATE)
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "transform: none !important" in css
    assert 'id="lka-explorer-fallback"' in html
    assert 'class="lka-fallback"' in html

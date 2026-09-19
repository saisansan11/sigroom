from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_explorer_uses_scoped_live_region():
    template = _read("templates/lodging/lodging_about.html")
    aside_open = template.split('<aside class="lka-room-panel"', 1)[1].split(">", 1)[0]

    assert "aria-live=" not in aside_open
    assert 'id="lka-panel-status" aria-live="polite" aria-atomic="true"' in template


def test_explorer_preserves_focus_and_restores_it_on_escape():
    script = _read("static/js/lodging_about_explorer.js")

    assert "focusedRoomNumber" in script
    assert "replacement.focus({ preventScroll: true })" in script
    assert "closePanel({ restoreFocus = false } = {})" in script
    assert "closePanel({ restoreFocus: true })" in script
    assert "document.addEventListener('keydown'" in script


def test_playwright_axe_gate_covers_public_routes():
    spec = _read("tests/a11y/public-routes.spec.js")

    for route in ("/", "/accounts/login/", "/lodging/", "/lodging/about/"):
        assert f"'{route}'" in spec
    assert "AxeBuilder" in spec
    assert "wcag22aa" in spec


def test_pr_safety_gate_requires_accessibility_audit():
    workflow = _read(".github/workflows/pr-safety-gate.yml")

    assert "accessibility-audit:" in workflow
    assert "name: Accessibility audit" in workflow
    assert "- accessibility-audit" in workflow
    assert "ACCESSIBILITY_AUDIT: ${{ needs.accessibility-audit.result }}" in workflow
    assert '[[ "$ACCESSIBILITY_AUDIT" == "success" ]]' in workflow

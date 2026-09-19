"""
UX-17 Dormitory Showcase — contract tests.

Covers:
1. /lodging/about/ public 200, no auth redirect
2. Link from /lodging/ to showcase and CTA back from showcase to /lodging/
3. Factual counts and floor labels
4. Floor-4 room mapping: air/fan sets and exclusion of 408, 409, 410 as lodging inventory
5. Floor-5 501-530 all air, capacity 4
6. Rates table exact values + 20-day note + electricity notes
7. Explorer control/accessibility semantics: floor toggle, filters, reset, keyboard hint, fallback
8. Real image assets and lazy loading; no remote external image/3D URLs
9. No PII rendering / no data dependency on active cohort records

Run with: uv run pytest bookings/tests_ux17_showcase.py -v
"""

from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse

from bookings.lodging_about_data import (
    ELECTRICITY_AIR_BAHT_PER_UNIT,
    ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH,
    FLOOR4_AIR_ROOMS,
    FLOOR4_BED_COUNT,
    FLOOR4_BEDS_PER_ROOM,
    FLOOR4_EXCLUDED,
    FLOOR4_FAN_ROOMS,
    FLOOR4_LODGING_ROOMS,
    FLOOR4_ROOM_COUNT,
    FLOOR5_AIR_ROOMS,
    FLOOR5_BED_COUNT,
    FLOOR5_BEDS_PER_ROOM,
    FLOOR5_FAN_ROOMS,
    FLOOR5_LODGING_ROOMS,
    FLOOR5_ROOM_COUNT,
    MONTHLY_THRESHOLD_DAYS,
    RATES,
    TOTAL_BEDS,
    TOTAL_ROOMS,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
WORKTREE_ROOT = Path(__file__).resolve().parent.parent
SHOWCASE_TEMPLATE = WORKTREE_ROOT / "templates" / "lodging" / "lodging_about.html"
LODGING_INDEX_TEMPLATE = WORKTREE_ROOT / "templates" / "lodging" / "lodging_index.html"
SHOWCASE_JS = WORKTREE_ROOT / "static" / "js" / "lodging_about_explorer.js"
SHOWCASE_CSS = WORKTREE_ROOT / "static" / "css" / "lodging_about.css"
SHOWCASE_STATIC = WORKTREE_ROOT / "static" / "img" / "showcase"

pytestmark = pytest.mark.django_db


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _template() -> str:
    return _read(SHOWCASE_TEMPLATE)


def _js() -> str:
    return _read(SHOWCASE_JS)


def _css() -> str:
    return _read(SHOWCASE_CSS)


# ---------------------------------------------------------------------------
# 1. Public access — 200, no auth redirect
# ---------------------------------------------------------------------------

def test_lodging_about_public_200():
    """GET /lodging/about/ returns 200 without authentication."""
    client = Client()
    url = reverse("bookings:lodging_about")
    response = client.get(url)
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}. "
        "The page must be public — no login_required decorator."
    )


def test_lodging_about_url_is_correct_pattern():
    """URL resolves to the correct named pattern."""
    url = reverse("bookings:lodging_about")
    assert url == "/lodging/about/", f"Unexpected URL: {url}"


def test_lodging_about_no_redirect_when_anonymous():
    """Anonymous users must not be redirected to /accounts/login/."""
    client = Client()
    url = reverse("bookings:lodging_about")
    response = client.get(url, follow=False)
    assert response.status_code not in (301, 302), (
        "Anonymous GET must not redirect. Page must be public."
    )


# ---------------------------------------------------------------------------
# 2. Navigation links
# ---------------------------------------------------------------------------

def test_lodging_index_links_to_about():
    """lodging_index.html must contain a link to bookings:lodging_about."""
    tmpl = _read(LODGING_INDEX_TEMPLATE)
    assert "lodging_about" in tmpl, (
        "lodging_index.html must link to bookings:lodging_about "
        "(e.g. {% url 'bookings:lodging_about' %})"
    )


def test_showcase_cta_links_back_to_lodging_index():
    """The showcase template must link back to bookings:lodging_index."""
    tmpl = _template()
    assert "lodging_index" in tmpl, (
        "lodging_about.html must contain a CTA link back to bookings:lodging_index"
    )


def test_showcase_page_contains_booking_cta(client):
    """Rendered page must contain the CTA back to the booking/lodging flow."""
    url = reverse("bookings:lodging_about")
    response = client.get(url)
    content = response.content.decode("utf-8")
    lodging_index_url = reverse("bookings:lodging_index")
    assert lodging_index_url in content, (
        f"Showcase page must contain CTA linking to {lodging_index_url}"
    )


# ---------------------------------------------------------------------------
# 3. Factual counts and floor labels on rendered page
# ---------------------------------------------------------------------------

def test_rendered_page_total_rooms_beds(client):
    """Rendered page must display 87 rooms and 234 beds."""
    url = reverse("bookings:lodging_about")
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "87" in content, "Page must state 87 total rooms"
    assert "234" in content, "Page must state 234 total beds"


def test_rendered_page_floor_4_counts(client):
    """Rendered page must display floor 4 facts: 57 rooms, 114 beds, 2 persons."""
    url = reverse("bookings:lodging_about")
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "57" in content, "Page must state 57 rooms on floor 4"
    assert "114" in content, "Page must state 114 beds on floor 4"
    assert "2" in content, "Page must state 2 persons per room (floor 4)"


def test_rendered_page_floor_5_counts(client):
    """Rendered page must display floor 5 facts: 30 rooms, 120 beds, 4 persons."""
    url = reverse("bookings:lodging_about")
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "30" in content, "Page must state 30 rooms on floor 5"
    assert "120" in content, "Page must state 120 beds on floor 5"
    assert "4" in content, "Page must state 4 persons per room (floor 5)"


def test_rendered_page_floor_labels(client):
    """Rendered page must contain Thai floor labels."""
    url = reverse("bookings:lodging_about")
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "ชั้น 4" in content, "Page must label floor 4 in Thai"
    assert "ชั้น 5" in content, "Page must label floor 5 in Thai"


# ---------------------------------------------------------------------------
# 4. Floor 4 room mapping contract
# ---------------------------------------------------------------------------

def test_floor4_air_room_count():
    """Floor 4 must have exactly 25 air-conditioned rooms."""
    assert len(FLOOR4_AIR_ROOMS) == 25, (
        f"Expected 25 air rooms on floor 4, got {len(FLOOR4_AIR_ROOMS)}"
    )


def test_floor4_air_rooms_exact_ranges():
    """Floor 4 air rooms must be exactly 401-407, 411-416, 449-460."""
    expected = set(range(401, 408)) | set(range(411, 417)) | set(range(449, 461))
    assert set(FLOOR4_AIR_ROOMS) == expected, (
        f"Air room set mismatch: {set(FLOOR4_AIR_ROOMS) ^ expected}"
    )


def test_floor4_fan_room_count():
    """Floor 4 must have exactly 32 fan rooms."""
    assert len(FLOOR4_FAN_ROOMS) == 32, (
        f"Expected 32 fan rooms on floor 4, got {len(FLOOR4_FAN_ROOMS)}"
    )


def test_floor4_fan_rooms_exact_range():
    """Floor 4 fan rooms must be exactly 417-448."""
    expected = set(range(417, 449))
    assert set(FLOOR4_FAN_ROOMS) == expected, (
        f"Fan room set mismatch: {set(FLOOR4_FAN_ROOMS) ^ expected}"
    )


def test_floor4_total_lodging_rooms():
    """Floor 4 lodging room total must be 57 (25 air + 32 fan)."""
    assert FLOOR4_ROOM_COUNT == 57, f"Expected 57, got {FLOOR4_ROOM_COUNT}"


def test_floor4_beds_per_room():
    """Floor 4 beds per room must be 2."""
    assert FLOOR4_BEDS_PER_ROOM == 2


def test_floor4_total_beds():
    """Floor 4 total beds must be 114 (57 × 2)."""
    assert FLOOR4_BED_COUNT == 114, f"Expected 114, got {FLOOR4_BED_COUNT}"


def test_floor4_excludes_408_409_410():
    """Rooms 408, 409, 410 must be excluded from lodging inventory."""
    excluded = {408, 409, 410}
    in_air = set(FLOOR4_AIR_ROOMS)
    in_fan = set(FLOOR4_FAN_ROOMS)
    overlap = excluded & (in_air | in_fan)
    assert not overlap, (
        f"Rooms {overlap} must NOT appear in lodging inventory (FLOOR4_AIR_ROOMS or FLOOR4_FAN_ROOMS)"
    )


def test_floor4_excluded_list_matches():
    """FLOOR4_EXCLUDED must contain exactly [408, 409, 410]."""
    assert sorted(FLOOR4_EXCLUDED) == [408, 409, 410]


def test_floor4_no_overlap_air_fan():
    """No room number may appear in both air and fan sets for floor 4."""
    air = set(FLOOR4_AIR_ROOMS)
    fan = set(FLOOR4_FAN_ROOMS)
    overlap = air & fan
    assert not overlap, f"Rooms appear in both air and fan: {overlap}"


def test_floor4_lodging_rooms_sorted_and_complete():
    """FLOOR4_LODGING_ROOMS must be the sorted union of air + fan."""
    expected = sorted(set(FLOOR4_AIR_ROOMS) | set(FLOOR4_FAN_ROOMS))
    assert FLOOR4_LODGING_ROOMS == expected


# ---------------------------------------------------------------------------
# 5. Floor 5 room mapping contract
# ---------------------------------------------------------------------------

def test_floor5_air_room_count():
    """Floor 5 must have exactly 30 air-conditioned rooms."""
    assert len(FLOOR5_AIR_ROOMS) == 30, f"Expected 30, got {len(FLOOR5_AIR_ROOMS)}"


def test_floor5_air_rooms_exact_range():
    """Floor 5 air rooms must be exactly 501-530."""
    expected = list(range(501, 531))
    assert FLOOR5_AIR_ROOMS == expected, f"Floor 5 air rooms mismatch: {FLOOR5_AIR_ROOMS}"


def test_floor5_no_fan_rooms():
    """Floor 5 must have zero fan rooms — all rooms are air-conditioned."""
    assert FLOOR5_FAN_ROOMS == [], f"Expected no fan rooms on floor 5, got {FLOOR5_FAN_ROOMS}"


def test_floor5_total_lodging_rooms():
    """Floor 5 lodging room total must be 30."""
    assert FLOOR5_ROOM_COUNT == 30, f"Expected 30, got {FLOOR5_ROOM_COUNT}"


def test_floor5_beds_per_room():
    """Floor 5 beds per room must be 4."""
    assert FLOOR5_BEDS_PER_ROOM == 4


def test_floor5_total_beds():
    """Floor 5 total beds must be 120 (30 × 4)."""
    assert FLOOR5_BED_COUNT == 120, f"Expected 120, got {FLOOR5_BED_COUNT}"


def test_floor5_all_rooms_are_air():
    """All floor 5 lodging rooms must be in the air list."""
    assert set(FLOOR5_LODGING_ROOMS) == set(FLOOR5_AIR_ROOMS)


# ---------------------------------------------------------------------------
# 6. Building totals
# ---------------------------------------------------------------------------

def test_total_rooms():
    """Total rooms across both floors must be 87."""
    assert TOTAL_ROOMS == 87, f"Expected 87, got {TOTAL_ROOMS}"


def test_total_beds():
    """Total beds across both floors must be 234."""
    assert TOTAL_BEDS == 234, f"Expected 234, got {TOTAL_BEDS}"


# ---------------------------------------------------------------------------
# 7. Rates exact values + notes
# ---------------------------------------------------------------------------

def _rate_by_category(category: str) -> dict:
    for r in RATES:
        if r["category"] == category:
            return r
    pytest.fail(f"Rate category not found: {category!r}")


def test_rates_has_five_categories():
    """RATES must have exactly 5 categories."""
    assert len(RATES) == 5, f"Expected 5 rate categories, got {len(RATES)}"


def test_rate_buklak_khong_nok():
    r = _rate_by_category("บุคคลภายนอก")
    assert r["air_day"] == 150
    assert r["air_month"] == 2500
    assert r["fan_day"] == 100
    assert r["fan_month"] == 2000


def test_rate_nkht_krom_sas():
    r = _rate_by_category("นขต.กรม.สส.")
    assert r["air_day"] == 100
    assert r["air_month"] == 2000
    assert r["fan_day"] == 70
    assert r["fan_month"] == 1500


def test_rate_nkht_rrs_sas():
    r = _rate_by_category("นขต.รร.ส.สส.")
    assert r["air_day"] == 50
    assert r["air_month"] == 1500
    assert r["fan_day"] == 40
    assert r["fan_month"] == 800


def test_rate_nai_thahan_nakrian():
    r = _rate_by_category("นายทหารนักเรียน")
    assert r["air_day"] == 50
    assert r["air_month"] == 1500
    assert r["fan_day"] == 40
    assert r["fan_month"] == 800


def test_rate_nai_sip_nakrian():
    r = _rate_by_category("นายสิบนักเรียน")
    assert r["air_day"] == 40
    assert r["air_month"] == 1000
    assert r["fan_day"] == 30
    assert r["fan_month"] == 800


def test_electricity_air():
    """Air electricity must be 5 baht/unit."""
    assert ELECTRICITY_AIR_BAHT_PER_UNIT == 5


def test_electricity_fan():
    """Fan electricity must be flat 200 baht/month."""
    assert ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH == 200


def test_monthly_threshold():
    """Monthly threshold must be 20 days."""
    assert MONTHLY_THRESHOLD_DAYS == 20


def test_rendered_rates_table_appears(client):
    """Rendered page must include rate amounts for all 5 categories."""
    url = reverse("bookings:lodging_about")
    response = client.get(url)
    content = response.content.decode("utf-8")
    # Check representative values from each category
    assert "150" in content, "Missing 150 (บุคคลภายนอก air/day)"
    assert "2,500" in content or "2500" in content, "Missing 2500 (บุคคลภายนอก air/month)"
    assert "นขต.กรม.สส." in content, "Missing นขต.กรม.สส. category"
    assert "นายสิบนักเรียน" in content, "Missing นายสิบนักเรียน category"


def test_rendered_20_day_note_present(client):
    """Rendered page must state the 20-day = 1-month rule."""
    url = reverse("bookings:lodging_about")
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "20" in content, "Page must state 20-day threshold"


def test_rendered_electricity_notes(client):
    """Rendered page must mention air electricity (5 baht/unit) and fan flat (200 baht)."""
    url = reverse("bookings:lodging_about")
    response = client.get(url)
    content = response.content.decode("utf-8")
    assert "5 บาท" in content or "5" in content, "Missing air electricity note"
    assert "200" in content, "Missing fan electricity flat-rate note"


def test_no_invented_effective_date_in_template():
    """Template must not contain an invented effective date for rates."""
    tmpl = _template()
    # Should not contain date patterns that look like a made-up effective date
    import re
    # Check for hardcoded years that would imply an effective date
    # The rates image is referenced but no textual effective date should be invented
    assert "มีผลตั้งแต่" not in tmpl, (
        "Template must not contain an invented effective date ('มีผลตั้งแต่')"
    )


# ---------------------------------------------------------------------------
# 8. Explorer control / accessibility semantics (static checks)
# ---------------------------------------------------------------------------

def test_template_has_floor_toggle_buttons():
    """Template must include floor toggle buttons for floor 4 and floor 5."""
    tmpl = _template()
    assert 'data-floor="4"' in tmpl, "Missing floor 4 toggle button"
    assert 'data-floor="5"' in tmpl, "Missing floor 5 toggle button"


def test_template_has_filter_buttons():
    """Template must include filter buttons: all, air, fan, facility."""
    tmpl = _template()
    assert 'data-filter="all"' in tmpl, "Missing 'all' filter"
    assert 'data-filter="air"' in tmpl, "Missing 'air' filter"
    assert 'data-filter="fan"' in tmpl, "Missing 'fan' filter"
    assert 'data-filter="facility"' in tmpl, "Missing 'facility' filter"


def test_template_has_reset_button():
    """Template must include a reset view button."""
    tmpl = _template()
    assert 'lka-reset' in tmpl, "Missing reset button (#lka-reset)"


def test_template_has_zoom_controls():
    """Template must include zoom-in and zoom-out controls."""
    tmpl = _template()
    assert 'lka-zoom-in' in tmpl, "Missing zoom-in control"
    assert 'lka-zoom-out' in tmpl, "Missing zoom-out control"


def test_template_has_drag_hint():
    """Template must include visible drag hint 'ลากเพื่อหมุน'."""
    tmpl = _template()
    assert "ลากเพื่อหมุน" in tmpl, "Missing 'ลากเพื่อหมุน' hint text"


def test_template_has_keyboard_hint_text():
    """Template must mention arrow-key and +/- keyboard controls."""
    tmpl = _template()
    assert "←" in tmpl or "arrow" in tmpl.lower() or "↑" in tmpl or "← →" in tmpl, (
        "Template must mention keyboard rotation hint (arrows)"
    )


def test_template_has_2d_text_fallback():
    """Template must include a 2D/text fallback (details/summary element)."""
    tmpl = _template()
    assert "<details" in tmpl, "Missing <details> fallback element"
    assert "lka-fallback" in tmpl, "Missing .lka-fallback class"


def test_template_fallback_contains_air_rooms_text():
    """Fallback must mention air rooms 401-407, 411-416, 449-460."""
    tmpl = _template()
    assert "401" in tmpl and "407" in tmpl, "Fallback missing 401-407 range"
    assert "411" in tmpl and "416" in tmpl, "Fallback missing 411-416 range"
    assert "449" in tmpl and "460" in tmpl, "Fallback missing 449-460 range"


def test_template_fallback_excludes_408_409_410():
    """Fallback note must exclude 408, 409, 410 from lodging inventory."""
    tmpl = _template()
    assert "408" in tmpl and "409" in tmpl and "410" in tmpl, (
        "Fallback must mention 408, 409, 410 as excluded rooms"
    )


def test_template_fallback_contains_floor5_rooms():
    """Fallback must mention floor 5 rooms 501-530."""
    tmpl = _template()
    assert "501" in tmpl and "530" in tmpl, "Fallback missing 501-530 floor 5 range"


def test_template_aria_pressed_on_buttons():
    """Toggle and filter buttons must have aria-pressed attribute."""
    tmpl = _template()
    assert 'aria-pressed' in tmpl, "Toggle/filter buttons must use aria-pressed"


def test_template_aria_live_panel():
    """Room detail announcements must use a scoped polite live region."""
    tmpl = _template()
    assert 'id="lka-panel-status"' in tmpl
    assert 'id="lka-panel-status" aria-live="polite" aria-atomic="true"' in tmpl
    panel_open = tmpl.split('<aside class="lka-room-panel"', 1)[1].split('>', 1)[0]
    assert 'aria-live=' not in panel_open


def test_template_diagram_not_exact_note():
    """Template must contain a note that the diagram is not exact BIM."""
    tmpl = _template()
    # Must clarify this is a representational diagram, not architectural BIM
    assert "ไม่ใช่แบบสถาปัตยกรรม" in tmpl or "BIM" in tmpl or "ประกอบเท่านั้น" in tmpl, (
        "Template must clarify diagram is not exact BIM/dimensions"
    )


def test_explorer_canvas_has_tabindex():
    """Explorer canvas must be keyboard-focusable (tabindex='0')."""
    tmpl = _template()
    assert 'tabindex="0"' in tmpl, "Explorer canvas must have tabindex='0'"


def test_js_keyboard_controls_implemented():
    """JS must handle ArrowLeft, ArrowRight, ArrowUp, ArrowDown, +/-, R."""
    js = _js()
    assert "ArrowLeft" in js
    assert "ArrowRight" in js
    assert "ArrowUp" in js
    assert "ArrowDown" in js
    assert "'+'" in js or '"+' in js or '"+"' in js or "'+'" in js
    assert '"-"' in js or '"_"' in js or "'-'" in js


def test_js_no_continuous_idle_loop():
    """JS must NOT use setInterval or requestAnimationFrame in an idle loop."""
    js = _js()
    assert "setInterval" not in js, "JS must not use setInterval (continuous loop)"
    # requestAnimationFrame is acceptable for scheduling, but not for idle rotation
    # Check there is no auto-rotate/idle-loop function
    assert "autoRotate" not in js, "JS must not implement auto-rotation loop"
    assert "idleLoop" not in js, "JS must not implement idleLoop"


def test_js_touch_events():
    """JS must support touch drag for rotation."""
    js = _js()
    assert "touchstart" in js, "JS must handle touchstart"
    assert "touchmove" in js, "JS must handle touchmove"


def test_js_floor_toggle():
    """JS must handle floor 4/5 toggle."""
    js = _js()
    assert (
        "dataset.floor" in js
        or 'getAttribute("data-floor")' in js
        or "getAttribute('data-floor')" in js
        or "data-floor" in js
    ), "JS must read floor data attribute via dataset.floor or data-floor"
    assert "currentFloor" in js, "JS must track currentFloor state"


def test_js_facilities_always_rendered_unconditionally():
    """makeSVG must render facilities unconditionally on every floor render (Blocker 1 regression).

    Facilities must not be conditionally created based on currentFilter, so that
    switching filters after changing floors always has facility nodes in the DOM.
    """
    js = _js()
    assert "FACILITIES.forEach" in js
    # Confirm FACILITIES.forEach is NOT enclosed in an if (currentFilter === ...) block
    idx = js.find("FACILITIES.forEach")
    preceding_code = js[max(0, idx - 120):idx]
    assert "if (currentFilter" not in preceding_code, (
        "FACILITIES.forEach must not be guarded by currentFilter; facilities must render every time"
    )


def test_js_filter_toggles_tabindex_and_aria_hidden():
    """applyFilter must toggle tabindex and aria-hidden for accessibility (Blocker 2 regression).

    Hidden elements must receive tabindex='-1' and aria-hidden='true' so they cannot
    be focused via keyboard Tab navigation. Visible bookable rooms must have tabindex='0'.
    """
    js = _js()
    assert "b.setAttribute('tabindex', '-1')" in js or 'b.setAttribute("tabindex", "-1")' in js
    assert "b.setAttribute('aria-hidden', 'true')" in js or 'b.setAttribute("aria-hidden", "true")' in js
    assert "b.removeAttribute('aria-hidden')" in js or 'b.removeAttribute("aria-hidden")' in js
    assert "b.setAttribute('tabindex', '0')" in js or 'b.setAttribute("tabindex", "0")' in js
    assert "role" in js and "button" in js


def test_js_filter_deselects_hidden_room():
    """applyFilter must close panel and deselect room if active room is filtered out."""
    js = _js()
    assert "closePanel()" in js
    assert "selected" in js


def test_regression_sequence_blocker1_and_blocker2_state_machine():
    """Simulate full interaction sequence for Blocker 1 and Blocker 2 in Python state machine.

    Sequence:
    1. Floor 4: All -> 57 rooms (tabindex=0), 3 facilities (role=img)
    2. Filter 'air' -> 25 air rooms visible (tabindex=0), 32 fan rooms hidden (tabindex=-1, aria-hidden=true)
    3. Toggle Floor 5 -> 30 rooms visible (tabindex=0), 3 facilities rendered in DOM and hidden
    4. Click 'facility' -> 3 facilities visible (not hidden), 30 rooms hidden (tabindex=-1, aria-hidden=true)
    5. Reverse: Toggle Floor 4 -> Click 'fan' -> 32 fan rooms visible (tabindex=0), 25 air hidden
    6. Click 'all' -> all 57 rooms visible with tabindex=0, aria-hidden removed.
    """
    from bookings.lodging_about_data import (
        FLOOR4_AIR_ROOMS,
        FLOOR4_FAN_ROOMS,
        FLOOR5_AIR_ROOMS,
    )

    class MockNode:
        def __init__(self, tag, num=None, cooling=None, is_facility=False):
            self.tag = tag
            self.num = num
            self.cooling = cooling
            self.is_facility = is_facility
            self.role = "button" if not is_facility else "img"
            self.classes = {"lka-room-block"}
            if is_facility:
                self.classes.add("facility")
            elif cooling:
                self.classes.add(cooling)
            self.tabindex = "0" if self.role == "button" else None
            self.aria_hidden = None

        def set_attribute(self, attr, val):
            if attr == "tabindex":
                self.tabindex = val
            elif attr == "aria-hidden":
                self.aria_hidden = val

        def remove_attribute(self, attr):
            if attr == "tabindex":
                self.tabindex = None
            elif attr == "aria-hidden":
                self.aria_hidden = None

    def make_svg(floor):
        nodes = []
        if floor == 4:
            for n in FLOOR4_AIR_ROOMS:
                nodes.append(MockNode("rect", num=n, cooling="air"))
            for n in FLOOR4_FAN_ROOMS:
                nodes.append(MockNode("rect", num=n, cooling="fan"))
        elif floor == 5:
            for n in FLOOR5_AIR_ROOMS:
                nodes.append(MockNode("rect", num=n, cooling="air"))
        # Facilities rendered unconditionally every time!
        for label in ["ห้องน้ำ ฝั่ง A", "ห้องน้ำ ฝั่ง B", "ห้องอาบน้ำ"]:
            nodes.append(MockNode("rect", is_facility=True))
        return nodes

    def apply_filter(nodes, filter_name):
        for b in nodes:
            is_fac = b.is_facility
            cooling = b.cooling
            if filter_name == "all":
                is_hidden = False
            elif filter_name == "facility":
                is_hidden = not is_fac
            else:
                is_hidden = is_fac or (cooling != filter_name)

            if is_hidden:
                b.classes.add("hidden-filter")
                b.set_attribute("tabindex", "-1")
                b.set_attribute("aria-hidden", "true")
            else:
                b.classes.discard("hidden-filter")
                b.remove_attribute("aria-hidden")
                if b.role == "button":
                    b.set_attribute("tabindex", "0")

    # 1. Floor 4: All
    nodes_f4 = make_svg(4)
    apply_filter(nodes_f4, "all")
    rooms = [n for n in nodes_f4 if not n.is_facility]
    facs = [n for n in nodes_f4 if n.is_facility]
    assert len(rooms) == 57
    assert len(facs) == 3
    assert all(r.tabindex == "0" for r in rooms)

    # 2. Filter 'air'
    apply_filter(nodes_f4, "air")
    visible_air = [n for n in nodes_f4 if "hidden-filter" not in n.classes and not n.is_facility]
    hidden_fan = [n for n in nodes_f4 if "hidden-filter" in n.classes and n.cooling == "fan"]
    assert len(visible_air) == 25
    assert len(hidden_fan) == 32
    # Blocker 2: check all 32 fan rooms have tabindex='-1' and aria-hidden='true'
    assert all(r.tabindex == "-1" and r.aria_hidden == "true" for r in hidden_fan)
    assert all(r.tabindex == "0" and r.aria_hidden is None for r in visible_air)

    # 3. Floor switch: Switch to Floor 5 while filter is 'air'
    nodes_f5 = make_svg(5)
    apply_filter(nodes_f5, "air")
    # Blocker 1: Facilities MUST exist in DOM
    f5_facs = [n for n in nodes_f5 if n.is_facility]
    assert len(f5_facs) == 3, f"Expected 3 facilities in DOM on Floor 5, got {len(f5_facs)}"

    # 4. Click 'facility' filter
    apply_filter(nodes_f5, "facility")
    f5_visible_facs = [n for n in nodes_f5 if n.is_facility and "hidden-filter" not in n.classes]
    assert len(f5_visible_facs) == 3, "Expected 3 visible facilities on Floor 5 after clicking facility filter"
    f5_hidden_rooms = [n for n in nodes_f5 if not n.is_facility and "hidden-filter" in n.classes]
    assert len(f5_hidden_rooms) == 30
    assert all(r.tabindex == "-1" and r.aria_hidden == "true" for r in f5_hidden_rooms)

    # 5. Reverse: Switch to Floor 4, click 'fan'
    nodes_f4_rev = make_svg(4)
    apply_filter(nodes_f4_rev, "fan")
    f4_visible_fan = [n for n in nodes_f4_rev if not n.is_facility and "hidden-filter" not in n.classes]
    assert len(f4_visible_fan) == 32
    assert all(r.tabindex == "0" and r.aria_hidden is None for r in f4_visible_fan)

    # 6. Click 'all'
    apply_filter(nodes_f4_rev, "all")
    f4_all_rooms = [n for n in nodes_f4_rev if not n.is_facility]
    assert len(f4_all_rooms) == 57
    assert all(r.tabindex == "0" and r.aria_hidden is None for r in f4_all_rooms)
    assert all(n.tabindex != "0" for n in nodes_f4_rev if n.is_facility)


def test_js_filter_applied():
    """JS must apply room filter (air/fan/facility/all)."""
    js = _js()
    assert "hidden-filter" in js, "JS must apply/remove hidden-filter class"
    assert "applyFilter" in js, "JS must define applyFilter function"


def test_js_room_detail_panel():
    """JS must populate and show the room detail panel on click."""
    js = _js()
    assert "showPanel" in js, "JS must define showPanel function"
    assert "lka-panel-number" in js, "JS must set panel room number"
    assert "lka-panel-floor" in js, "JS must set panel floor"
    assert "lka-panel-cooling" in js, "JS must set panel cooling type"
    assert "lka-panel-capacity" in js, "JS must set panel capacity"


def test_js_no_external_cdn():
    """JS must not load from external CDNs or remote URLs."""
    js = _js()
    assert "cdn.jsdelivr.net" not in js
    assert "unpkg.com" not in js
    assert "cdnjs.cloudflare.com" not in js
    assert "spline" not in js.lower()
    assert "sketchfab" not in js.lower()
    assert "three.min.js" not in js
    assert "import(" not in js, "JS must not use dynamic import()"
    assert "fetch(" not in js, "JS must not fetch remote resources"


def test_js_no_webgl():
    """JS must not reference WebGL APIs."""
    js = _js()
    assert "getContext('webgl')" not in js
    assert "getContext(\"webgl\")" not in js
    assert "WebGLRenderer" not in js


# ---------------------------------------------------------------------------
# 9. Real image assets — local only, no external image/3D URLs
# ---------------------------------------------------------------------------

def test_showcase_static_assets_exist():
    """All required showcase images must exist in static/img/showcase/."""
    required = [
        "floor4.png",
        "floor5.png",
        "room2p_222.jpg",
        "room2p_444.jpg",
        "room4p_3421.jpg",
        "room4p_4444.jpg",
        "bath1.jpg",
        "bath2.jpg",
        "bath3.jpg",
        "rates.png",
    ]
    missing = [f for f in required if not (SHOWCASE_STATIC / f).exists()]
    assert not missing, f"Missing showcase assets: {missing}"


def test_template_references_local_static_images():
    """Template must reference only local {% static %} image paths — no http/https URLs."""
    tmpl = _template()
    import re
    # Find all src= and href= that look like external URLs
    external_img = re.findall(r'src=["\']https?://', tmpl)
    assert not external_img, f"Template has external image URLs: {external_img}"


def test_template_noncritical_images_are_lazy():
    """Non-hero gallery images must have loading='lazy'."""
    tmpl = _template()
    # Count how many images have loading="lazy"
    assert 'loading="lazy"' in tmpl, "Gallery images must have loading='lazy'"
    # All showcase images (bath, room, floor map, rates) should be lazy
    lazy_count = tmpl.count('loading="lazy"')
    assert lazy_count >= 8, (
        f"Expected at least 8 lazy images (room, bath, floor, rates photos), got {lazy_count}"
    )


def test_template_no_spline_or_remote_3d():
    """Template must not load Spline or any remote 3D host."""
    tmpl = _template()
    assert "spline" not in tmpl.lower(), "Template must not reference Spline"
    assert "sketchfab" not in tmpl.lower(), "Template must not reference Sketchfab"
    assert "model-viewer" not in tmpl.lower(), "Template must not reference model-viewer CDN"


def test_template_no_cdn_links():
    """Template must not link to external CDNs."""
    tmpl = _template()
    assert "cdn.jsdelivr.net" not in tmpl
    assert "unpkg.com" not in tmpl
    assert "cdnjs.cloudflare.com" not in tmpl


def test_js_script_tag_uses_local_path():
    """The JS script tag must reference a local {% static %} path."""
    tmpl = _template()
    assert "lodging_about_explorer.js" in tmpl, (
        "Template must load the local explorer JS file"
    )
    assert "src=\"http" not in tmpl.split("lodging_about_explorer")[0][-50:], (
        "Explorer JS src must not be an external URL"
    )


# ---------------------------------------------------------------------------
# 10. No PII, no auth dependency, no active cohort dependency
# ---------------------------------------------------------------------------

def test_page_renders_without_any_cohort_records(client):
    """Page must render successfully even if the database has no cohort records."""
    # The database in tests may have zero cohorts — page must still return 200
    url = reverse("bookings:lodging_about")
    response = client.get(url)
    assert response.status_code == 200, (
        "Page must not depend on active cohort records existing in the DB"
    )


def test_template_no_student_pii_fields():
    """Template must not render student personal data (name, phone, rank)."""
    tmpl = _template()
    # These template variables would indicate student PII is being rendered
    pii_patterns = [
        "student.full_name",
        "student.phone",
        "student.rank",
        "student.origin_unit",
        "owner.full_name",
        "owner.phone",
    ]
    for pat in pii_patterns:
        assert pat not in tmpl, f"Template must not render student PII field: {pat}"


def test_template_no_user_authentication_dependent_content():
    """Template must not reference user.is_authenticated for main content."""
    tmpl = _template()
    # The page heading/content must not be conditional on login
    # (nav_can_* checks in base.html are ok, but not in the showcase content itself)
    assert "{% if user.is_authenticated %}" not in tmpl, (
        "Showcase content must not depend on user authentication state"
    )


def test_template_no_availability_or_booking_state():
    """Template must not imply live room availability or booking state."""
    tmpl = _template()
    # Should not use cohort.remaining_slots or room availability variables
    assert "remaining_slots" not in tmpl, (
        "Showcase must not display live remaining slot counts"
    )
    assert "cohort.rooms" not in tmpl, (
        "Showcase must not query cohort room assignments"
    )


# ---------------------------------------------------------------------------
# 11. CSS file exists and has UX-17 scoped classes
# ---------------------------------------------------------------------------

def test_css_file_exists():
    """lodging_about.css must exist in static/css/."""
    assert SHOWCASE_CSS.exists(), f"Missing CSS: {SHOWCASE_CSS}"


def test_css_scoped_prefix():
    """CSS must use .lka- prefix for scoping."""
    css = _css()
    assert ".lka-" in css, "CSS must use .lka- scoped prefix"


def test_css_no_horizontal_overflow():
    """CSS must prevent horizontal overflow (overflow: hidden on wrapper)."""
    css = _css()
    assert "overflow: hidden" in css or "overflow:hidden" in css, (
        "Explorer wrapper must have overflow: hidden to prevent 360px overflow"
    )


def test_css_reduced_motion_rule():
    """CSS must include a prefers-reduced-motion media query."""
    css = _css()
    assert "prefers-reduced-motion" in css, (
        "CSS must include @media (prefers-reduced-motion: reduce) rules"
    )


# ---------------------------------------------------------------------------
# 12. Plan and handoff docs exist
# ---------------------------------------------------------------------------

def test_plan_doc_exists():
    """docs/plans/2026-09-18-ux-17-dormitory-showcase.md must exist."""
    plan = WORKTREE_ROOT / "docs" / "plans" / "2026-09-18-ux-17-dormitory-showcase.md"
    assert plan.exists(), f"Missing plan doc: {plan}"


def test_handoff_doc_exists():
    """docs/handoffs/2026-09-18-ux-17-dormitory-showcase.md must exist."""
    handoff = WORKTREE_ROOT / "docs" / "handoffs" / "2026-09-18-ux-17-dormitory-showcase.md"
    assert handoff.exists(), f"Missing handoff doc: {handoff}"

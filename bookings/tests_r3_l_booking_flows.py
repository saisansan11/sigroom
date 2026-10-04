from pathlib import Path

import pytest
from django.urls import reverse


ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.django_db


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_general_lodging_request_is_one_short_public_form(client):
    response = client.get(reverse("bookings:lodging_general_request"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")

    assert "ขอใช้ห้องพัก" in html
    assert "เลือกวันเข้า–ออกและจำนวนผู้พักก่อน" in html
    assert "วันเสาร์และอาทิตย์เลือกได้" in html
    assert 'class="r3l-request-sheet"' in html
    for field in ("check_in", "check_out", "attendees", "guest_name", "phone", "note"):
        assert f'name="{field}"' in html
    assert 'formmethod="get"' in html  # A5: no-JS room refresh and attendee +/- fallback
    assert 'id="public-room-picker"' in html
    assert "ช่วงนี้ห้องเต็ม" in html  # no room select is rendered when the inventory is empty
    assert "ส่งคำขอ" in html


def test_online_teaching_booking_exposes_one_primary_submit_action():
    template = _read("templates/bookings/online_teaching_book.html")

    assert 'name="action" value="book"' in template
    assert 'name="action" value="check"' not in template
    assert "ตรวจสอบช่วงเวลา" not in template
    assert "ระบบตรวจห้องว่างและเวลาซ้ำอีกครั้งเมื่อกดยืนยัน" in template
    assert "ยืนยันการจอง" in template


def test_student_lodging_portal_has_compact_summary_and_preserves_bed_flow():
    template = _read("templates/lodging/student_portal.html")

    assert 'class="lodging-r3l-summary"' in template
    assert "ว่าง {{ free_slots }} จาก {{ total_slots }} เตียง" in template
    assert "เลือกเตียงว่าง" in template
    assert "openBookingModal" in template
    assert "roomGalleryStep" in template
    assert "lodging_book_bed" in template


def test_keycard_flip_is_explicitly_preserved_in_r3_l():
    template = _read("templates/lodging/student_pass.html")
    include = '{% include "partials/cassette_pass.html" %}'
    assert template.count(include) == 1
    template = template.replace(include, _read("templates/partials/cassette_pass.html"))
    cassette_js = _read("static/js/lodging_cassette_pass.js")

    assert template.count('id="keycard"') == 1
    assert "keycard-front" in template
    assert "keycard-back" in template
    assert "lodging_cassette_pass.js" in template
    assert "<script>" not in template
    assert "แตะบัตรหรือกด Enter / Space เพื่อพลิกดู QR" in template

    # B6 keeps the same flip/keyboard contract, but moves behavior out of the template.
    assert "toggleFlip" in cassette_js
    assert "is-flipped" in cassette_js
    assert "keydown" in cassette_js
    assert "Enter" in cassette_js
    assert "Spacebar" in cassette_js
    assert "aria-pressed" in cassette_js


def test_r3_l_overlays_do_not_reintroduce_decorative_gradients():
    lodging_css = _read("static/css/lodging_booking_r3l.css")
    online_css = _read("static/css/online_teaching_r3l.css")

    assert "linear-gradient" not in lodging_css
    assert "radial-gradient" not in lodging_css
    assert "linear-gradient" not in online_css
    assert "radial-gradient" not in online_css
    assert "min-height: 44px" in lodging_css
    assert "min-height: 44px" in online_css

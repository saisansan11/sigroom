"""UX-33 lodging visual convergence regression tests (login journey retired in theme A)."""
from pathlib import Path



ROOT = Path(__file__).resolve().parent.parent
PORTAL = ROOT / "templates" / "lodging" / "student_portal.html"
LOGIN = ROOT / "templates" / "registration" / "login.html"
CSS = ROOT / "static" / "css" / "lodging_booking_ios27.css"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_student_portal_uses_light_ios27_booking_surface():
    html = _text(PORTAL)
    assert "{% block html_theme %}light{% endblock %}" in html
    assert "{% block body_class %}lodging-booking-ios27{% endblock %}" in html
    assert "lodging_booking_ios27.css" in html
    assert 'class="student-lodging-portal"' in html
    assert "🔒" not in html and "🖼" not in html


def test_booking_dialog_preserves_single_existing_booking_flow_with_richer_context():
    html = _text(PORTAL)
    assert html.count('id="bookingModal"') == 1
    assert 'aria-labelledby="bookingModalHeading"' in html
    assert 'aria-describedby="bookingModalHint"' in html
    assert 'class="booking-dialog-icon"' in html
    assert 'class="booking-dialog-kicker"' in html
    assert "เลือกห้องพัก" in html
    assert "document.getElementById('bookingModalHint').textContent" in html
    assert "bookingDialog.addEventListener('close'" in html

    # UX work must not fork or rename the booking contract.
    assert "{% url 'bookings:lodging_book_bed' cohort.slug %}" in html
    for field in ("room_id", "bed_number", "rank", "full_name", "origin_unit", "phone", "note"):
        assert f'name="{field}"' in html


def test_booking_css_matches_bright_info_page_and_dark_reference_dialog():
    css = _text(CSS)
    assert "body.lodging-booking-ios27" in css
    # ธีม A Ledger: สีถูก re-map เป็นกระดาษ/หมึก ไม่มีสีฟ้า-ม่วงแบบ iOS เหลืออยู่
    assert "#F5F1E6" in css
    assert "#bookingModal::backdrop" in css
    assert "#278bd2" not in css and "#6440c9" not in css
    assert "#f4f6fa" not in css
    assert "@media (max-width: 47.99rem)" in css
    assert "grid-template-columns: minmax(0, .72fr) minmax(0, 1.28fr)" in css


# ผู้ใช้ตัดสินใจ 2 ต.ค. 2569: เลิกภาพทหาร/กระเป๋าเคลื่อนไหวบนหน้าเข้าสู่ระบบ ใช้แผ่นแบบฟอร์มกระดาษ (ธีม A)
# ชุดทดสอบหน้าเข้าสู่ระบบแบบใหม่อยู่ที่ accounts/tests_login_ledger.py


def test_login_has_no_arrival_illustration_or_journey_css():
    html = _text(LOGIN)
    assert "arrival-" not in html
    assert "sigroom-login-journey" not in html
    assert "lodging_booking_ios27.css" not in html
    css = _text(CSS)
    assert "sigroom-login-journey" not in css
    assert "@keyframes sigroom-soldier-arrive" not in css
    assert "@keyframes sigroom-login-rise" not in css

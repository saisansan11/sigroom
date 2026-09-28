"""UX-33 lodging visual convergence and login arrival journey regression tests."""
from pathlib import Path

import pytest


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
    assert "Room selection" in html
    assert "document.getElementById('bookingModalHint').textContent" in html
    assert "bookingDialog.addEventListener('close'" in html

    # UX work must not fork or rename the booking contract.
    assert "{% url 'bookings:lodging_book_bed' cohort.slug %}" in html
    for field in ("room_id", "bed_number", "rank", "full_name", "origin_unit", "phone", "note"):
        assert f'name="{field}"' in html


def test_booking_css_matches_bright_info_page_and_dark_reference_dialog():
    css = _text(CSS)
    assert "body.lodging-booking-ios27" in css
    assert "#f4f6fa" in css
    assert "rgba(255, 255, 255, .91)" in css
    assert "#bookingModal::backdrop" in css
    assert "linear-gradient(145deg, #171d2e" in css
    assert "linear-gradient(90deg, #278bd2, #6440c9)" in css
    assert "@media (max-width: 47.99rem)" in css
    assert "grid-template-columns: minmax(0, .72fr) minmax(0, 1.28fr)" in css


def test_login_uses_non_emoji_vector_soldier_suitcase_journey():
    html = _text(LOGIN)
    assert "{% block body_class %}sigroom-login-journey{% endblock %}" in html
    assert 'class="arrival-soldier"' in html
    assert 'class="arrival-suitcase"' in html
    assert 'class="arrival-suitcase-lid"' in html
    assert 'class="login-card"' in html
    assert "sigroom-login-journey-seen-v1" in html
    assert "prefers-reduced-motion: reduce" in html
    assert "journey-skip" in html
    assert "journey-play" in html
    assert "🚀" not in html and "🧳" not in html and "🪖" not in html


def test_login_animation_is_progressive_enhancement_and_reduced_motion_safe():
    css = _text(CSS)
    assert "@keyframes sigroom-soldier-arrive" in css
    assert "@keyframes sigroom-suitcase-drop" in css
    assert "@keyframes sigroom-suitcase-open" in css
    assert "@keyframes sigroom-login-rise" in css
    assert "body.sigroom-login-journey.journey-skip .login-card" in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    reduced = css.split("@media (prefers-reduced-motion: reduce)", 1)[1]
    assert "animation: none !important" in reduced
    assert "body.sigroom-login-journey .login-card" in reduced


@pytest.mark.django_db
def test_login_page_renders_journey_and_existing_recovery_link(client):
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'class="arrival-soldier"' in html
    assert 'class="arrival-suitcase"' in html
    assert 'id="id_username"' in html
    assert 'id="id_password"' in html
    assert 'href="/accounts/password-reset/"' in html

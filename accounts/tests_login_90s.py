from pathlib import Path

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parent.parent


def test_login_timecard_preserves_auth_contract_and_hides_google(client):
    target = reverse("bookings:my_bookings")
    response = client.get(reverse("login"), {"next": target})
    assert response.status_code == 200
    html = response.content.decode("utf-8")

    assert 'class="login-punch-clock"' in html
    assert 'aria-hidden="true"' in html
    assert "บัตรลงเวลาเข้าระบบ" in html
    assert "ตอกบัตรเข้าระบบ" in html
    assert 'name="username"' in html and 'id="id_username"' in html
    assert 'autocomplete="username"' in html
    assert 'name="password"' in html and 'id="id_password"' in html
    assert 'autocomplete="current-password"' in html
    assert f'name="next" value="{target}"' in html
    assert "csrfmiddlewaretoken" in html
    assert "เข้าสู่ระบบด้วย Google" not in html
    assert "google-login-standard" not in html
    assert response.context["google_login_enabled"] is False
    assert response.context["login_now"] is not None
    assert reverse("bookings:lodging_start") in html


def test_auth_recovery_pages_share_manila_timecard_frame(client):
    for name in (
        "accounts:password_reset",
        "accounts:password_reset_done",
        "accounts:password_reset_complete",
    ):
        response = client.get(reverse(name))
        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert "timecard-sheet" in html
        assert "auth-manila-card" in html
        assert "login-punch-clock" not in html

    logged_out = (ROOT / "templates" / "registration" / "logged_out.html").read_text(encoding="utf-8")
    assert "timecard-sheet" in logged_out
    assert "auth-manila-card" in logged_out
    assert "login-punch-clock" not in logged_out


def test_first_password_change_template_uses_manila_frame_without_clock():
    template = (ROOT / "templates" / "accounts" / "first_password_change.html").read_text(encoding="utf-8")
    assert "timecard-sheet" in template
    assert "auth-manila-card" in template
    assert "login-punch-clock" not in template


def test_b9_theme_keeps_google_button_standard_and_avoids_ruled_background():
    css = (ROOT / "static" / "css" / "theme_90s.css").read_text(encoding="utf-8")
    login = (ROOT / "templates" / "registration" / "login.html").read_text(encoding="utf-8")

    assert "/* B9 — หน้าเข้าสู่ระบบแบบเครื่องตอกบัตร" in css
    assert ".google-login-standard" in css
    assert "#4285F4" in login and "#34A853" in login and "#FBBC05" in login and "#EA4335" in login
    b9_css = css.split("/* B9 — หน้าเข้าสู่ระบบแบบเครื่องตอกบัตร", 1)[1]
    assert "repeating-linear-gradient" not in b9_css
    assert "background-image" not in b9_css
    assert "prefers-reduced-motion: reduce" in b9_css

"""หน้าเข้าสู่ระบบแบบแผ่นแบบฟอร์มกระดาษ (ธีม A) — แทนภาพทหาร/กระเป๋าเคลื่อนไหว (ผู้ใช้ตัดสิน 2 ต.ค. 2569)"""
import pytest
from django.urls import reverse

from accounts.models import Unit, User

pytestmark = pytest.mark.django_db
GOOD = "Password-2569"


@pytest.fixture
def user():
    unit = Unit.objects.create(code="LEDG", name="แผนกทดสอบ")
    return User.objects.create_user(username="ledger_login", email="ledger_login@signalschool.ac.th", password=GOOD, unit=unit)


def test_login_page_is_plain_form_sheet(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "เข้าสู่ระบบ SIGROOM" in html
    assert "ระบบจองห้อง รร.ส.สส." in html
    assert 'class="auth-sheet login-sheet timecard-sheet"' in html
    for leftover in ("arrival-soldier", "arrival-suitcase", "<svg class=\"arrival", "sigroom-login-journey", "lodging_booking_ios27.css"):
        assert leftover not in html
    assert 'id="id_username"' in html and 'id="id_password"' in html
    assert 'href="/accounts/password-reset/"' in html
    assert "ติดต่อผู้ดูแลระบบ" in html
    assert reverse("bookings:lodging_start") in html  # B9/A1: ทางเข้าที่พักสาธารณะผ่านตัวเลือกประเภทผู้พัก
    assert "csrfmiddlewaretoken" in html


def test_login_still_logs_in_and_honours_next(client, user):
    target = reverse("bookings:my_bookings")
    page = client.get(reverse("login"), {"next": target}).content.decode()
    assert f'name="next" value="{target}"' in page
    response = client.post(reverse("login"), {"username": "ledger_login", "password": GOOD, "next": target})
    assert response.status_code == 302 and response["Location"] == target
    assert "_auth_user_id" in client.session


def test_login_error_keeps_username_and_thai_message(client, user):
    response = client.post(reverse("login"), {"username": "ledger_login", "password": "wrong"})
    html = response.content.decode()
    assert "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง" in html
    assert 'aria-invalid="true"' in html
    assert 'value="ledger_login"' in html


def test_auth_pages_share_sheet_layout(client):
    for name in ("accounts:password_reset", "accounts:password_reset_done"):
        html = client.get(reverse(name)).content.decode()
        assert 'class="auth-sheet timecard-sheet auth-manila-card"' in html
        assert "auth-card" not in html

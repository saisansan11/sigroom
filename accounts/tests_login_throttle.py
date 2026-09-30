"""จำกัดจำนวนครั้งที่ใส่รหัสผ่านผิดที่หน้า login (ระบบเปิดผ่านอินเทอร์เน็ต — กันสุ่มรหัสผ่าน)"""
from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from accounts.services import LOGIN_THROTTLED_MESSAGE, login_is_throttled
from audit.models import AuditLog

pytestmark = pytest.mark.django_db

GOOD = "Password-2569"
# proxy ตัวเดียว: IP ผู้ใช้คือค่าท้ายสุดของ X-Forwarded-For ตรง ๆ (ทำให้ทดสอบเปลี่ยน IP ได้)
TRUSTED = {"CLIENT_IP_HEADER": "", "TRUSTED_PROXY_HOPS": 1}


@pytest.fixture
def user():
    unit = Unit.objects.create(code="COMM", name="แผนกวิชาการสื่อสาร")
    return User.objects.create_user(
        username="somchai", email="somchai@signalschool.ac.th", password=GOOD, unit=unit
    )


def _login(client, username, password, ip):
    return client.post(reverse("login"), {"username": username, "password": password}, HTTP_X_FORWARDED_FOR=ip)


def _logged_in(client) -> bool:
    return "_auth_user_id" in client.session


def _fail_times(client, username, ip, times):
    for _ in range(times):
        _login(client, username, "wrong", ip)


@override_settings(**TRUSTED)
def test_wrong_password_shows_generic_error_not_throttle_message(client, user):
    response = _login(client, "somchai", "wrong", "198.51.100.1")
    assert response.status_code == 200
    assert response.context["login_throttled"] is False
    assert "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง" in response.content.decode()


@override_settings(**TRUSTED)
def test_correct_password_still_logs_in_below_limit(client, user):
    _fail_times(client, "somchai", "198.51.100.1", 4)
    _login(client, "somchai", GOOD, "198.51.100.1")
    assert _logged_in(client)


@override_settings(**TRUSTED)
def test_user_ip_limit_blocks_even_correct_password(client, user):
    _fail_times(client, "somchai", "198.51.100.1", 5)
    response = _login(client, "somchai", GOOD, "198.51.100.1")
    assert not _logged_in(client)
    assert response.status_code == 200
    assert response.context["login_throttled"] is True
    assert LOGIN_THROTTLED_MESSAGE in response.content.decode()


@override_settings(**TRUSTED)
def test_blocked_attempts_do_not_write_more_audit_rows(client, user):
    _fail_times(client, "somchai", "198.51.100.1", 5)
    before = AuditLog.objects.filter(action="login_failed").count()
    _fail_times(client, "somchai", "198.51.100.1", 3)
    assert AuditLog.objects.filter(action="login_failed").count() == before


@override_settings(**TRUSTED)
def test_other_ip_can_still_log_in_when_one_ip_is_blocked(client, user):
    _fail_times(client, "somchai", "198.51.100.1", 5)
    _login(client, "somchai", GOOD, "203.0.113.50")
    assert _logged_in(client)


@override_settings(**TRUSTED, LOGIN_THROTTLE_USER_LIMIT=4)
def test_username_limit_blocks_rotating_ips(client, user):
    for index in range(4):  # เปลี่ยน IP ทุกครั้งเพื่อหลบเพดานต่อ IP
        _login(client, "somchai", "wrong", f"198.51.100.{index + 1}")
    _login(client, "somchai", GOOD, "203.0.113.77")
    assert not _logged_in(client)


@override_settings(**TRUSTED, LOGIN_THROTTLE_IP_LIMIT=3)
def test_ip_limit_blocks_spraying_many_usernames(client, user):
    for index in range(3):
        _login(client, f"nobody{index}", "wrong", "198.51.100.9")
    response = _login(client, "somchai", GOOD, "198.51.100.9")
    assert not _logged_in(client)
    assert response.context["login_throttled"] is True


@override_settings(**TRUSTED)
def test_limit_relaxes_after_window(client, user):
    _fail_times(client, "somchai", "198.51.100.1", 5)
    assert login_is_throttled("somchai", "198.51.100.1")
    later = timezone.now() + timedelta(seconds=901)
    assert not login_is_throttled("somchai", "198.51.100.1", now=later)


@override_settings(**TRUSTED)
def test_unknown_username_is_throttled_like_a_real_one(client, user):
    # ไม่เปิดช่องให้ใช้ผลการบล็อกเดาว่าชื่อผู้ใช้มีอยู่จริงหรือไม่
    _fail_times(client, "ghost", "198.51.100.1", 5)
    response = _login(client, "ghost", "wrong", "198.51.100.1")
    assert response.context["login_throttled"] is True

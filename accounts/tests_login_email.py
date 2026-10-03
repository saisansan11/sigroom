import pytest
from django.test import override_settings
from django.urls import reverse

from accounts.models import Unit, User
from audit.models import AuditLog

pytestmark = pytest.mark.django_db

GOOD = "Password-2569"
TRUSTED = {"CLIENT_IP_HEADER": "", "TRUSTED_PROXY_HOPS": 1}


@pytest.fixture
def user():
    unit = Unit.objects.create(code="AUTH-EMAIL", name="หน่วยทดสอบเข้าสู่ระบบ")
    return User.objects.create_user(
        username="somchai",
        email="somchai@signalschool.ac.th",
        password=GOOD,
        unit=unit,
    )


def _login(client, identity, password=GOOD, ip="198.51.100.10"):
    return client.post(
        reverse("login"),
        {"username": identity, "password": password},
        HTTP_X_FORWARDED_FOR=ip,
    )


def _is_logged_in(client):
    return "_auth_user_id" in client.session


@override_settings(**TRUSTED)
def test_login_accepts_registered_unit_email_case_insensitively(client, user):
    response = _login(client, "Somchai@SignalSchool.ac.th")
    assert response.status_code == 302
    assert _is_logged_in(client)


@override_settings(**TRUSTED)
def test_login_by_username_still_works(client, user):
    response = _login(client, "somchai")
    assert response.status_code == 302
    assert _is_logged_in(client)


@pytest.mark.parametrize(
    "identity,password",
    [
        ("somchai@gmail.com", GOOD),
        ("nobody@signalschool.ac.th", GOOD),
        ("somchai@signalschool.ac.th", "wrong-password"),
    ],
)
@override_settings(**TRUSTED)
def test_rejected_email_cases_keep_same_generic_error(client, user, identity, password):
    response = _login(client, identity, password)
    assert response.status_code == 200
    body = response.content.decode()
    assert "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง" in body
    assert "อีเมลต้องเป็นบัญชีของหน่วย" not in body
    assert not _is_logged_in(client)


@override_settings(**TRUSTED)
def test_inactive_account_cannot_login_by_email(client, user):
    user.is_active = False
    user.save(update_fields=["is_active"])
    response = _login(client, "somchai@signalschool.ac.th")
    assert response.status_code == 200
    assert not _is_logged_in(client)


@override_settings(**TRUSTED, LOGIN_THROTTLE_USER_IP_LIMIT=5)
def test_username_and_email_share_same_throttle_identity(client, user):
    for _ in range(4):
        _login(client, "somchai", "wrong-password")
    fifth = _login(client, "SOMCHAI@signalschool.ac.th", "wrong-password")
    assert fifth.status_code == 200

    # The fifth failure is stored under the same canonical key as the username.
    assert AuditLog.objects.filter(action="login_failed", entity_id="somchai").count() == 5

    blocked = _login(client, "somchai@signalschool.ac.th", GOOD)
    assert blocked.status_code == 200
    assert blocked.context["login_throttled"] is True
    assert not _is_logged_in(client)


def test_login_page_labels_username_or_unit_email(client):
    response = client.get(reverse("login"))
    assert response.status_code == 200
    body = response.content.decode()
    assert "ชื่อผู้ใช้ หรืออีเมลหน่วย" in body
    assert 'placeholder="เช่น somchai หรืออีเมลหน่วย"' in body
    assert 'autocomplete="username"' in body

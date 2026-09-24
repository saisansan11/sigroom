import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail

from audit.models import AuditLog

from .models import Unit, User


@pytest.fixture(autouse=True)
def password_reset_email_test_settings(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.DEFAULT_FROM_EMAIL = "SIGROOM <noreply@signalschool.ac.th>"
    settings.SECURE_SSL_REDIRECT = False
    settings.PASSWORD_RESET_TIMEOUT = 3600
    mail.outbox = []


@pytest.fixture
def reset_user(db):
    unit = Unit.objects.create(code="SELFRESET", name="หน่วยทดสอบลืมรหัส")
    return User.objects.create_user(
        username="self-reset",
        email="self-reset@signalschool.ac.th",
        password="Old-Sigroom-Password-2570!",
        unit=unit,
        must_change_password=True,
    )


def _reset_link_from_latest_email():
    assert mail.outbox
    match = re.search(r"https?://[^\s]+", mail.outbox[-1].body)
    assert match, mail.outbox[-1].body
    return match.group(0)


@pytest.mark.django_db
def test_login_shows_self_service_password_reset_link(client):
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "ลืมรหัสผ่าน?" in content
    assert 'href="/accounts/password-reset/"' in content


@pytest.mark.django_db
def test_reset_request_is_anti_enumeration_for_known_and_unknown_email(client, reset_user):
    known = client.post("/accounts/password-reset/", {"email": reset_user.email.upper()})
    assert known.status_code == 302
    assert known.url == "/accounts/password-reset/done/"
    assert len(mail.outbox) == 1

    unknown = client.post("/accounts/password-reset/", {"email": "nobody@signalschool.ac.th"})
    assert unknown.status_code == known.status_code
    assert unknown.url == known.url
    assert len(mail.outbox) == 1

    done = client.get(unknown.url)
    body = done.content.decode("utf-8")
    assert done.status_code == 200
    assert "หากอีเมลที่กรอกตรงกับบัญชี SIGROOM" in body
    assert "nobody@signalschool.ac.th" not in body


@pytest.mark.django_db
def test_reset_request_rejects_non_unit_domain_without_sending_email(client):
    response = client.post("/accounts/password-reset/", {"email": "person@example.com"})
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "@signalschool.ac.th" in body
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_legacy_django_reset_url_is_shadowed_by_unit_domain_guard(client):
    response = client.post("/accounts/password_reset/", {"email": "person@example.com"})
    assert response.status_code == 200
    assert "@signalschool.ac.th" in response.content.decode("utf-8")
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_reset_email_uses_namespaced_one_time_link(client, reset_user):
    response = client.post("/accounts/password-reset/", {"email": reset_user.email}, secure=True)
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [reset_user.email]
    assert message.from_email == "SIGROOM <noreply@signalschool.ac.th>"
    assert "ตั้งรหัสผ่าน SIGROOM ใหม่" in message.subject

    link = _reset_link_from_latest_email()
    parsed = urlparse(link)
    assert parsed.scheme == "https"
    assert parsed.path.startswith("/accounts/password-reset/confirm/")
    assert "Old-Sigroom-Password" not in message.body


@pytest.mark.django_db
def test_valid_reset_changes_password_clears_initial_flag_and_writes_secret_free_audit(client, reset_user):
    client.post("/accounts/password-reset/", {"email": reset_user.email})
    original_link = _reset_link_from_latest_email()
    original_path = urlparse(original_link).path
    token = original_path.rstrip("/").split("/")[-1]

    first = client.get(original_path)
    assert first.status_code == 302
    set_password_path = first.url
    assert set_password_path.endswith("/set-password/")

    new_password = "New-Sigroom-Recovery-Password-2570!"
    changed = client.post(
        set_password_path,
        {"new_password1": new_password, "new_password2": new_password},
    )
    assert changed.status_code == 302
    assert changed.url == "/accounts/password-reset/complete/"

    reset_user.refresh_from_db()
    assert reset_user.check_password(new_password)
    assert not reset_user.check_password("Old-Sigroom-Password-2570!")
    assert reset_user.must_change_password is False

    row = AuditLog.objects.get(
        entity="accounts.user",
        entity_id=str(reset_user.pk),
        action="password_reset_self_service",
    )
    assert row.actor_id == reset_user.pk
    assert row.before == {"must_change_password": True, "password_usable": True}
    assert row.after == {
        "must_change_password": False,
        "password_changed": True,
        "reset_via": "self_service_email",
    }
    audit_text = f"{row.before!r}{row.after!r}"
    assert new_password not in audit_text
    assert token not in audit_text
    assert "argon2" not in audit_text and "pbkdf2_" not in audit_text
    assert not AuditLog.objects.filter(
        entity="accounts.user",
        entity_id=str(reset_user.pk),
        action="registry_updated",
    ).exists()

    replay_client = client.__class__()
    replay = replay_client.get(original_path)
    assert replay.status_code == 200
    assert "ลิงก์ไม่ถูกต้องหรือหมดอายุ" in replay.content.decode("utf-8")


@pytest.mark.django_db
def test_reset_confirm_rejects_weak_password_without_audit(client, reset_user):
    client.post("/accounts/password-reset/", {"email": reset_user.email})
    original_path = urlparse(_reset_link_from_latest_email()).path
    first = client.get(original_path)
    assert first.status_code == 302

    weak = client.post(
        first.url,
        {"new_password1": "password", "new_password2": "password"},
    )
    assert weak.status_code == 200
    reset_user.refresh_from_db()
    assert reset_user.check_password("Old-Sigroom-Password-2570!")
    assert reset_user.must_change_password is True
    assert not AuditLog.objects.filter(action="password_reset_self_service").exists()


@pytest.mark.django_db
def test_reset_token_expires_at_configured_timeout(client, reset_user, monkeypatch, settings):
    settings.PASSWORD_RESET_TIMEOUT = 60
    issued_at = datetime(2026, 9, 24, 14, 0, 0)
    monkeypatch.setattr(default_token_generator, "_now", lambda: issued_at)
    client.post("/accounts/password-reset/", {"email": reset_user.email})
    original_path = urlparse(_reset_link_from_latest_email()).path

    monkeypatch.setattr(default_token_generator, "_now", lambda: issued_at + timedelta(seconds=61))
    expired = client.get(original_path)
    assert expired.status_code == 200
    assert "ลิงก์ไม่ถูกต้องหรือหมดอายุ" in expired.content.decode("utf-8")
    reset_user.refresh_from_db()
    assert reset_user.check_password("Old-Sigroom-Password-2570!")
    assert not AuditLog.objects.filter(action="password_reset_self_service").exists()

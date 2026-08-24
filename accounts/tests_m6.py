import csv
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command

from audit.models import AuditLog

from .models import Unit, User


@pytest.mark.django_db
def test_import_users_creates_valid_rows_skips_bad_and_writes_password_file(tmp_path):
    Unit.objects.create(code="GOOD", name="หน่วยจริง")
    source = tmp_path / "users.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["username", "email", "rank", "first_name", "last_name", "unit_code", "phone", "service_number"])
        writer.writerow(["real-user", "real-user@signalschool.ac.th", "ร.อ.", "จริง", "ใจดี", "GOOD", "1234", "S-001"])
        writer.writerow(["bad-user", "bad@example.com", "", "เสีย", "โดเมน", "MISSING", "", ""])
    stdout, stderr = StringIO(), StringIO()
    call_command("import_users", str(source), output_dir=str(tmp_path), stdout=stdout, stderr=stderr)
    user = User.objects.get(username="real-user")
    assert user.must_change_password is True
    assert not User.objects.filter(username="bad-user").exists()
    output = tmp_path / f"imported-users-{date.today():%Y%m%d}.csv"
    assert output.exists() and "ข้ามแถว 3" in stderr.getvalue()
    with output.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    assert rows[1][0] == "real-user" and len(rows[1][1]) == 12


@pytest.mark.django_db
def test_must_change_password_redirects_then_clears_flag_and_audits(client):
    unit = Unit.objects.create(code="PWD", name="หน่วยรหัสผ่าน")
    user = User.objects.create_user("first-login", "first-login@signalschool.ac.th", "Initial-Password-123", unit=unit, must_change_password=True)
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 302 and response.url == "/accounts/change-initial-password/"
    response = client.post("/accounts/change-initial-password/", {
        "old_password": "Initial-Password-123",
        "new_password1": "New-Sigroom-Password-2570!",
        "new_password2": "New-Sigroom-Password-2570!",
    })
    assert response.status_code == 302 and response.url == "/"
    user.refresh_from_db()
    assert user.must_change_password is False
    assert AuditLog.objects.filter(actor=user, action="initial_password_changed").exists()
    audit_text = "".join(f"{row.before!r}{row.after!r}" for row in AuditLog.objects.filter(actor=user))
    assert "argon2" not in audit_text and "pbkdf2_" not in audit_text


@pytest.mark.django_db
def test_must_change_password_uses_hx_redirect_for_htmx(client):
    unit = Unit.objects.create(code="HX", name="หน่วย HTMX")
    user = User.objects.create_user("hx-first-login", "hx-first-login@signalschool.ac.th", "Initial-Password-123", unit=unit, must_change_password=True)
    client.force_login(user)
    response = client.get("/api/calendar/events/", HTTP_HX_REQUEST="true")
    assert response.status_code == 204
    assert response.headers["HX-Redirect"] == "/accounts/change-initial-password/"


@pytest.mark.django_db
def test_seed_pilot_rerun_does_not_reset_existing_demo_password():
    call_command("seed_pilot", demo_users=True, stdout=StringIO())
    user = User.objects.get(username="somchai")
    user.set_password("User-Owned-Password-2570!")
    user.must_change_password = False
    user.save(update_fields=["password", "must_change_password"])
    call_command("seed_pilot", demo_users=True, stdout=StringIO())
    user.refresh_from_db()
    assert user.check_password("User-Owned-Password-2570!")
    assert user.must_change_password is False


@pytest.mark.django_db
def test_http_pilot_settings_do_not_redirect_to_https(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False
    response = client.get("/accounts/login/")
    assert response.status_code == 200
    assert response.get("Location") is None

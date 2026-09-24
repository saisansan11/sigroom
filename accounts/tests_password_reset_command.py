from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from audit.models import AuditLog

from .models import Unit, User


@pytest.fixture
def reset_users(db):
    unit = Unit.objects.create(code="RST", name="หน่วยทดสอบรีเซ็ตรหัส")
    operator = User.objects.create_superuser(
        username="reset-admin",
        email="reset-admin@signalschool.ac.th",
        password="Operator-Password-2570!",
        unit=unit,
    )
    target = User.objects.create_user(
        username="reset-target",
        email="reset-target@signalschool.ac.th",
        password="Old-Target-Password-2570!",
        unit=unit,
        must_change_password=False,
    )
    return operator, target


@pytest.mark.django_db
def test_reset_user_password_changes_only_target_and_writes_secret_free_audit(tmp_path, reset_users):
    operator, target = reset_users
    temporary_password = "Temporary-Sigroom-Password-2570!"
    password_file = tmp_path / "temporary-password.txt"
    password_file.write_text(temporary_password + "\n", encoding="utf-8")
    stdout = StringIO()

    call_command(
        "reset_user_password",
        target.username,
        operator=operator.username,
        password_file=str(password_file),
        confirm=f"RESET:{target.username}",
        stdout=stdout,
    )

    target.refresh_from_db()
    operator.refresh_from_db()
    assert target.check_password(temporary_password)
    assert not target.check_password("Old-Target-Password-2570!")
    assert target.must_change_password is True
    assert operator.check_password("Operator-Password-2570!")

    row = AuditLog.objects.get(
        entity="accounts.user",
        entity_id=str(target.pk),
        action="password_reset_by_admin_command",
    )
    assert row.actor_id == operator.pk
    assert row.before == {"must_change_password": False, "password_usable": True}
    assert row.after == {
        "must_change_password": True,
        "password_changed": True,
        "reset_via": "management_command",
    }
    audit_text = f"{row.before!r}{row.after!r}"
    assert temporary_password not in audit_text
    assert "pbkdf2_" not in audit_text
    assert "argon2" not in audit_text
    assert temporary_password not in stdout.getvalue()
    assert not AuditLog.objects.filter(
        entity="accounts.user",
        entity_id=str(target.pk),
        action="registry_updated",
    ).exists()


@pytest.mark.django_db
def test_reset_user_password_requires_active_superuser_operator(tmp_path, reset_users):
    _, target = reset_users
    unit = target.unit
    operator = User.objects.create_user(
        username="plain-operator",
        email="plain-operator@signalschool.ac.th",
        password="Plain-Operator-Password-2570!",
        unit=unit,
    )
    password_file = tmp_path / "temporary-password.txt"
    password_file.write_text("Temporary-Sigroom-Password-2570!\n", encoding="utf-8")

    with pytest.raises(CommandError, match="superuser"):
        call_command(
            "reset_user_password",
            target.username,
            operator=operator.username,
            password_file=str(password_file),
            confirm=f"RESET:{target.username}",
        )

    target.refresh_from_db()
    assert target.check_password("Old-Target-Password-2570!")
    assert not AuditLog.objects.filter(action="password_reset_by_admin_command").exists()


@pytest.mark.django_db
def test_reset_user_password_requires_exact_confirmation(tmp_path, reset_users):
    operator, target = reset_users
    password_file = tmp_path / "temporary-password.txt"
    password_file.write_text("Temporary-Sigroom-Password-2570!\n", encoding="utf-8")

    with pytest.raises(CommandError, match="--confirm RESET:reset-target"):
        call_command(
            "reset_user_password",
            target.username,
            operator=operator.username,
            password_file=str(password_file),
            confirm="RESET:wrong-user",
        )

    target.refresh_from_db()
    assert target.check_password("Old-Target-Password-2570!")
    assert target.must_change_password is False
    assert not AuditLog.objects.filter(action="password_reset_by_admin_command").exists()


@pytest.mark.django_db
def test_reset_user_password_dry_run_does_not_require_or_read_secret(reset_users):
    operator, target = reset_users
    stdout = StringIO()

    call_command(
        "reset_user_password",
        target.username,
        operator=operator.username,
        dry_run=True,
        stdout=stdout,
    )

    target.refresh_from_db()
    assert target.check_password("Old-Target-Password-2570!")
    assert target.must_change_password is False
    assert "DRY RUN PASS" in stdout.getvalue()
    assert not AuditLog.objects.filter(action="password_reset_by_admin_command").exists()


@pytest.mark.django_db
def test_reset_user_password_rejects_weak_password(tmp_path, reset_users):
    operator, target = reset_users
    password_file = tmp_path / "temporary-password.txt"
    password_file.write_text("password\n", encoding="utf-8")

    with pytest.raises(CommandError, match="รหัสผ่านไม่ผ่านนโยบาย"):
        call_command(
            "reset_user_password",
            target.username,
            operator=operator.username,
            password_file=str(password_file),
            confirm=f"RESET:{target.username}",
        )

    target.refresh_from_db()
    assert target.check_password("Old-Target-Password-2570!")
    assert target.must_change_password is False
    assert not AuditLog.objects.filter(action="password_reset_by_admin_command").exists()

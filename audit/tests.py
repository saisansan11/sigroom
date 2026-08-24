import pytest
from django.core.exceptions import ValidationError

from accounts.models import Unit, User

from .models import AuditLog
from .services import audit, model_snapshot


@pytest.mark.django_db
def test_audit_log_is_append_only_for_instance_and_queryset():
    row = audit(None, "test.entity", "1", "created", after={"ok": True})
    row.action = "changed"
    with pytest.raises(ValidationError):
        row.save()
    with pytest.raises(ValidationError):
        row.delete()
    with pytest.raises(ValidationError):
        AuditLog.objects.filter(pk=row.pk).update(action="changed")
    with pytest.raises(ValidationError):
        AuditLog.objects.filter(pk=row.pk).delete()


@pytest.mark.django_db
def test_login_failure_and_success_are_audited(client):
    unit = Unit.objects.create(code="AUD", name="หน่วย Audit")
    user = User.objects.create_user("audit-user", "audit-user@signalschool.ac.th", "Test-Password-123", unit=unit)
    assert not client.login(username="audit-user", password="wrong-password")
    assert AuditLog.objects.filter(action="login_failed", entity_id="audit-user").exists()
    assert client.login(username="audit-user", password="Test-Password-123")
    assert AuditLog.objects.filter(action="login", actor=user).count() == 1
    assert not AuditLog.objects.filter(entity="accounts.user", entity_id=str(user.pk), action="registry_updated").exists()


@pytest.mark.django_db
def test_user_snapshot_never_contains_password_hash_or_last_login():
    unit = Unit.objects.create(code="SAFE", name="หน่วยปลอดภัย")
    user = User.objects.create_user("safe-user", "safe-user@signalschool.ac.th", "Secret-Password-123", unit=unit)
    password_hash = user.password
    snapshot = model_snapshot(user)
    assert "password" not in snapshot and "last_login" not in snapshot
    user.set_password("Another-Secret-Password-456")
    user.save(update_fields=["password"])
    rows = AuditLog.objects.filter(entity="accounts.user", entity_id=str(user.pk))
    assert rows.filter(action="registry_updated", after__password_changed=True).exists()
    for row in rows:
        serialized = f"{row.before!r}{row.after!r}"
        assert password_hash not in serialized
        assert "pbkdf2_" not in serialized and "argon2" not in serialized


@pytest.mark.django_db
def test_six_explicit_audit_actions_create_separate_rows():
    actions = ["booking_created", "booking_submitted", "booking_updated", "booking_cancelled", "booking_approved", "preemption_executed"]
    for action in actions:
        audit(None, "bookings.booking", action, action)
    assert set(AuditLog.objects.filter(action__in=actions).values_list("action", flat=True)) == set(actions)

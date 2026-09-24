from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit.services import audit


@transaction.atomic
def complete_initial_password_change(user, raw_password):
    """ตั้งรหัสของผู้ใช้จริง ปิดธง S17 และบันทึกเหตุการณ์ใน transaction เดียว"""
    locked = get_user_model().objects.select_for_update().get(pk=user.pk)
    if not locked.must_change_password:
        raise ValueError("บัญชีนี้เปลี่ยนรหัสผ่านครั้งแรกเรียบร้อยแล้ว")
    validate_password(raw_password, locked)
    locked.set_password(raw_password)
    locked.must_change_password = False
    locked._audit_skip_registry = True
    locked.save(update_fields=["password", "must_change_password"])
    audit(
        locked,
        "accounts.user",
        locked.pk,
        "initial_password_changed",
        before={"must_change_password": True},
        after={"must_change_password": False, "password_changed": True},
    )
    return locked


@transaction.atomic
def reset_password_by_superuser(*, operator, target, raw_password):
    """Reset one active account, force first-login change, and append a secret-free audit row."""
    user_model = get_user_model()
    locked_operator = user_model.objects.select_for_update().get(pk=operator.pk)
    if not locked_operator.is_active or not locked_operator.is_superuser:
        raise PermissionDenied("ผู้ดำเนินการต้องเป็นบัญชี superuser ที่เปิดใช้งาน")

    locked_target = user_model.objects.select_for_update().get(pk=target.pk)
    if not locked_target.is_active:
        raise ValidationError("บัญชีเป้าหมายปิดใช้งานอยู่ จึงไม่รีเซ็ตรหัสผ่าน")

    validate_password(raw_password, locked_target)
    before = {
        "must_change_password": locked_target.must_change_password,
        "password_usable": locked_target.has_usable_password(),
    }
    locked_target.set_password(raw_password)
    locked_target.must_change_password = True
    locked_target._audit_skip_registry = True
    locked_target.save(update_fields=["password", "must_change_password"])
    audit_row = audit(
        locked_operator,
        "accounts.user",
        locked_target.pk,
        "password_reset_by_admin_command",
        before=before,
        after={
            "must_change_password": True,
            "password_changed": True,
            "reset_via": "management_command",
        },
    )
    return locked_target, audit_row

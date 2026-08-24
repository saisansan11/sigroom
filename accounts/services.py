from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
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

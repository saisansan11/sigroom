from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm

from .models import validate_allowed_email_domain
from .services import complete_self_service_password_reset


class FirstPasswordChangeForm(PasswordChangeForm):
    """ใช้ validator ชุดเดียวกับ Django และแสดงข้อความไทยจากระบบ"""


class UnitPasswordResetForm(PasswordResetForm):
    """รับเฉพาะอีเมลหน่วย และคงพฤติกรรม anti-enumeration ของ Django ไว้"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "อีเมลหน่วย"
        self.fields["email"].widget.attrs.update(
            {
                "autocomplete": "email",
                "placeholder": "ชื่อบัญชี@signalschool.ac.th",
            }
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        validate_allowed_email_domain(email)
        return email


class AuditedSetPasswordForm(SetPasswordForm):
    """ตั้งรหัสใหม่จาก reset token พร้อม audit โดยไม่เก็บ token หรือรหัสผ่าน"""

    def save(self, commit=True):
        # PasswordResetConfirmView เรียก save() แบบ commit=True เสมอ; คง signature
        # ของ Django ไว้ แต่ห้ามแยก password write ออกจาก audit transaction.
        if not commit:
            raise ValueError("AuditedSetPasswordForm ต้องบันทึกแบบ commit=True")
        user, _ = complete_self_service_password_reset(
            self.user,
            self.cleaned_data["new_password1"],
        )
        self.user = user
        return user

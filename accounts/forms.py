from django.contrib.auth.forms import PasswordChangeForm


class FirstPasswordChangeForm(PasswordChangeForm):
    """ใช้ validator ชุดเดียวกับ Django และแสดงข้อความไทยจากระบบ"""


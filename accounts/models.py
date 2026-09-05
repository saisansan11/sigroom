"""
ผู้ใช้และหน่วยงาน (SRS ข้อ 3, D8, SR-02)

- บัญชีสร้างโดยผู้ดูแลระบบเท่านั้น (ไม่มีหน้าสมัคร)
- อีเมลต้องลงท้ายด้วยโดเมนที่กำหนดใน settings.ALLOWED_EMAIL_DOMAIN
- บทบาท (ผู้อนุมัติ / เจ้าหน้าที่ดูแลห้อง) ผูกกับห้องใน resources ไม่ได้อยู่ที่นี่
"""
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models


def validate_allowed_email_domain(value: str) -> None:
    domain = settings.ALLOWED_EMAIL_DOMAIN.lower()
    if not value.lower().endswith("@" + domain):
        raise ValidationError(f"อีเมลต้องเป็นบัญชีของหน่วย (@{domain}) เท่านั้น")


class Unit(models.Model):
    """หน่วยงาน เช่น แผนกวิชา กองการศึกษา"""

    code = models.CharField("รหัสหน่วย", max_length=20, unique=True)
    name = models.CharField("ชื่อหน่วย", max_length=200)
    parent = models.ForeignKey(
        "self", verbose_name="หน่วยเหนือ", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    is_active = models.BooleanField("ใช้งาน", default=True)

    class Meta:
        verbose_name = "หน่วยงาน"
        verbose_name_plural = "หน่วยงาน"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"


class User(AbstractUser):
    """ผู้ใช้ระบบ — ใช้ username สำหรับเข้าสู่ระบบ และบังคับอีเมลของหน่วย"""

    email = models.EmailField("อีเมลหน่วย", unique=True, validators=[validate_allowed_email_domain])
    service_number = models.CharField("หมายเลขประจำตัว", max_length=20, unique=True, null=True, blank=True)
    rank = models.CharField("ยศ", max_length=50, blank=True)
    position = models.CharField("ตำแหน่ง", max_length=200, blank=True)
    phone = models.CharField("โทรศัพท์", max_length=30, blank=True)
    unit = models.ForeignKey(Unit, verbose_name="สังกัด", null=True, blank=True, on_delete=models.PROTECT, related_name="members")
    # ห้องโปรด (แผน V7 งาน C) — ห้องที่ติดดาวขึ้นก่อนในผลค้นหาและแถบว่างตอนนี้
    favorite_resources = models.ManyToManyField(
        "resources.Resource", verbose_name="ห้องโปรด", blank=True, related_name="favorited_by"
    )
    is_infosec_officer = models.BooleanField(
        "เจ้าหน้าที่ความมั่นคงสารสนเทศ", default=False, help_text="จัดกิจกรรมเป็นข้อมูลอ่อนไหวได้ (SRS SR-07)"
    )
    must_change_password = models.BooleanField(
        "ต้องเปลี่ยนรหัสผ่านเมื่อเข้าสู่ระบบครั้งถัดไป",
        default=False,
        help_text="ใช้กับบัญชีที่นำเข้าและบัญชีทดลอง ห้ามปิดจนกว่าผู้ใช้จะตั้งรหัสผ่านของตนเอง",
    )

    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = "ผู้ใช้"
        verbose_name_plural = "ผู้ใช้"

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        full = f"{self.rank} {self.get_full_name()}".strip()
        return full or self.username

    def clean(self) -> None:
        super().clean()
        if self.email:
            self.email = self.email.lower()
            validate_allowed_email_domain(self.email)

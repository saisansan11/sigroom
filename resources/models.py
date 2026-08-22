"""
ทะเบียนทรัพยากรที่จองได้ (SRS ข้อ 4) และกฎรายห้อง (SRS ข้อ 5)

"ห้อง" และ "อุปกรณ์ส่วนกลาง" เป็นทรัพยากรชนิดเดียวกัน ใช้กลไกตรวจเวลาชนร่วมกัน
อุปกรณ์ส่วนกลางไม่มีผู้อนุมัติ (ระยะที่ 1)
"""
from django.conf import settings
from django.db import models


class Resource(models.Model):
    class Type(models.TextChoices):
        ROOM = "room", "ห้อง"
        EQUIPMENT = "equipment", "อุปกรณ์ส่วนกลาง"

    class Category(models.TextChoices):
        CLASSROOM = "classroom", "ห้องเรียน"
        LAB = "lab", "ห้องสอนปฏิบัติ"
        MEETING = "meeting", "ห้องประชุม"
        SPECIAL = "special", "ห้องพิเศษ"
        NONE = "none", "— (อุปกรณ์)"

    class Status(models.TextChoices):
        ACTIVE = "active", "ใช้งาน"
        OUT_OF_SERVICE = "out_of_service", "งดใช้ชั่วคราว"
        RETIRED = "retired", "ปลดระวาง"

    resource_type = models.CharField("ประเภททรัพยากร", max_length=20, choices=Type.choices, default=Type.ROOM)
    code = models.CharField("รหัส", max_length=30, unique=True, help_text="เช่น B2-301 หรือ PROJ-05")
    name = models.CharField("ชื่อ", max_length=200)
    building = models.CharField("อาคาร", max_length=100, blank=True)
    floor = models.CharField("ชั้น", max_length=20, blank=True)
    location_note = models.CharField("ที่ตั้งเพิ่มเติม", max_length=200, blank=True)
    room_category = models.CharField("ประเภทห้อง", max_length=20, choices=Category.choices, default=Category.CLASSROOM)
    capacity = models.PositiveIntegerField("ความจุ (คน)", default=0, help_text="0 = ไม่กำหนด ระบบเตือนเมื่อเกิน ไม่บล็อก")
    fixed_equipment = models.TextField("อุปกรณ์ประจำห้อง", blank=True, help_text="บรรทัดละรายการ")
    layouts = models.TextField("รูปแบบจัดโต๊ะที่รองรับ", blank=True, help_text="บรรทัดละรายการ")
    owner_unit = models.ForeignKey(
        "accounts.Unit", verbose_name="หน่วยเจ้าของ", null=True, blank=True, on_delete=models.PROTECT, related_name="owned_resources"
    )
    custodians = models.ManyToManyField(
        settings.AUTH_USER_MODEL, verbose_name="เจ้าหน้าที่ดูแล", blank=True, related_name="custodied_resources"
    )
    status = models.CharField("สถานะ", max_length=20, choices=Status.choices, default=Status.ACTIVE)

    class Meta:
        verbose_name = "ทรัพยากร (ห้อง/อุปกรณ์)"
        verbose_name_plural = "ทรัพยากร (ห้อง/อุปกรณ์)"
        ordering = ["building", "code"]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    @property
    def is_room(self) -> bool:
        return self.resource_type == self.Type.ROOM


class ResourceRule(models.Model):
    """กฎรายทรัพยากร (SRS ข้อ 5) — หนึ่งแถวต่อหนึ่งทรัพยากร"""

    class ApprovalPolicy(models.TextChoices):
        AUTO = "auto", "อัตโนมัติเมื่อว่าง"
        REQUIRED = "required", "ต้องอนุมัติ"

    resource = models.OneToOneField(Resource, verbose_name="ทรัพยากร", on_delete=models.CASCADE, related_name="rule")
    approval_policy = models.CharField("นโยบายอนุมัติ", max_length=20, choices=ApprovalPolicy.choices, default=ApprovalPolicy.AUTO)
    allowed_units = models.ManyToManyField(
        "accounts.Unit", verbose_name="หน่วยที่จองได้", blank=True, help_text="เว้นว่าง = ทุกหน่วย"
    )
    max_advance_days = models.PositiveIntegerField("จองล่วงหน้าสูงสุด (วัน)", default=90)
    cancel_cutoff_hours = models.PositiveIntegerField("แก้ไข/ยกเลิกได้ถึงก่อนเริ่ม (ชม.)", default=4)
    buffer_before_min = models.PositiveIntegerField("Buffer ก่อน (นาที)", default=0)
    buffer_after_min = models.PositiveIntegerField("Buffer หลัง (นาที)", default=0)
    service_start = models.TimeField("เปิดให้บริการ", default="07:30")
    service_end = models.TimeField("ปิดให้บริการ", default="17:00")
    min_duration_min = models.PositiveIntegerField("ระยะจองขั้นต่ำ (นาที)", default=30)
    max_duration_min = models.PositiveIntegerField("ระยะจองสูงสุดต่อครั้ง (นาที)", default=24 * 60)
    allow_series = models.BooleanField("จองเป็นชุดได้", default=True)
    max_series_occurrences = models.PositiveIntegerField("จำนวนครั้งสูงสุดต่อชุด", default=20)

    class Meta:
        verbose_name = "กฎรายห้อง"
        verbose_name_plural = "กฎรายห้อง"

    def __str__(self) -> str:
        return f"กฎของ {self.resource.code}"


class ResourceApprover(models.Model):
    """ผู้อนุมัติของห้อง — แยกจากเจ้าของห้อง (SRS ข้อ 7) เฉพาะห้องเท่านั้น"""

    resource = models.ForeignKey(Resource, verbose_name="ห้อง", on_delete=models.CASCADE, related_name="approvers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="ผู้อนุมัติ", on_delete=models.PROTECT, related_name="approver_of")
    is_primary = models.BooleanField("ผู้อนุมัติหลัก", default=False, help_text="ไม่ติ๊ก = ผู้อนุมัติสำรอง")

    class Meta:
        verbose_name = "ผู้อนุมัติของห้อง"
        verbose_name_plural = "ผู้อนุมัติของห้อง"
        constraints = [
            models.UniqueConstraint(fields=["resource", "user"], name="uniq_approver_per_resource"),
            models.UniqueConstraint(
                fields=["resource"], condition=models.Q(is_primary=True), name="one_primary_approver_per_resource"
            ),
        ]

    def __str__(self) -> str:
        role = "หลัก" if self.is_primary else "สำรอง"
        return f"{self.user} ({role}) — {self.resource.code}"

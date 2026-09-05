"""
ทะเบียนทรัพยากรที่จองได้ (SRS ข้อ 4) และกฎรายห้อง (SRS ข้อ 5)

"ห้อง" และ "อุปกรณ์ส่วนกลาง" เป็นทรัพยากรชนิดเดียวกัน ใช้กลไกตรวจเวลาชนร่วมกัน
อุปกรณ์ส่วนกลางไม่มีผู้อนุมัติ (ระยะที่ 1)
"""
import uuid
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Resource(models.Model):
    class Type(models.TextChoices):
        ROOM = "room", "ห้อง"
        EQUIPMENT = "equipment", "อุปกรณ์ส่วนกลาง"

    class Category(models.TextChoices):
        CLASSROOM = "classroom", "ห้องเรียน"
        LAB = "lab", "ห้องสอนปฏิบัติ"
        MEETING = "meeting", "ห้องประชุม"
        LODGING = "lodging", "ห้องพัก"
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

    @property
    def cover_photo(self) -> "ResourcePhoto | None":
        """รูปหน้าปกของห้อง (งาน v6-c) — ResourcePhoto.Meta.ordering เรียง is_cover มาก่อนเสมอ
        ถ้าไม่มีรูปที่ตั้ง is_cover ไว้ จะได้รูปแรกตามลำดับแทนเพื่อไม่ให้การ์ดว่างเปล่าโดยไม่จำเป็น
        ใช้ .all() (ไม่ใช่ .first()) เพื่ออ่านจาก prefetch_related("photos") ถ้ามี ไม่ยิง query ซ้ำ (กัน N+1)
        """
        photos = list(self.photos.all())
        return photos[0] if photos else None

    @property
    def photo_url_list(self) -> list[str]:
        """URL รูปทั้งหมดของห้องตามลำดับ ใช้ป้อนแกลเลอรีในหน้าเว็บ — อ่านจาก prefetch cache เช่นกัน"""
        return [photo.image.url for photo in self.photos.all()]


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

    def clean(self):
        super().clean()
        if self.service_start and self.service_end and self.service_end <= self.service_start:
            raise ValidationError({"service_end": "เวลาปิดให้บริการต้องอยู่หลังเวลาเปิดในวันเดียวกัน"})

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


class Blackout(models.Model):
    class Scope(models.TextChoices):
        ALL = "all", "ทุกห้อง"
        BUILDING = "building", "อาคาร"
        CATEGORY = "category", "ประเภทห้อง"
        ROOMS = "rooms", "ห้องที่เลือก"

    title = models.CharField("ชื่อวันหยุด/กิจกรรม", max_length=200)
    start_at = models.DateTimeField("เริ่ม")
    end_at = models.DateTimeField("สิ้นสุด")
    scope = models.CharField("ขอบเขต", max_length=20, choices=Scope.choices, default=Scope.ALL)
    building = models.CharField("อาคาร", max_length=100, blank=True)
    room_category = models.CharField("ประเภทห้อง", max_length=20, choices=Resource.Category.choices, blank=True)
    rooms = models.ManyToManyField(
        Resource,
        verbose_name="ห้องที่เลือก",
        blank=True,
        related_name="blackouts",
        limit_choices_to={"resource_type": Resource.Type.ROOM},
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="สร้างโดย",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="created_blackouts",
    )

    class Meta:
        verbose_name = "ปฏิทินส่วนกลาง"
        verbose_name_plural = "ปฏิทินส่วนกลาง"
        ordering = ["start_at", "title"]
        constraints = [
            models.CheckConstraint(condition=models.Q(end_at__gt=models.F("start_at")), name="blackout_end_after_start")
        ]

    def applies_to(self, resource: Resource) -> bool:
        if self.scope == self.Scope.ALL:
            return True
        if self.scope == self.Scope.BUILDING:
            return bool(self.building and resource.building == self.building)
        if self.scope == self.Scope.CATEGORY:
            return bool(self.room_category and resource.room_category == self.room_category)
        return self.rooms.filter(pk=resource.pk).exists()

    def __str__(self):
        return f"{self.title} ({self.get_scope_display()})"


class ResourceOutage(models.Model):
    resource = models.ForeignKey(
        Resource,
        verbose_name="ห้อง",
        on_delete=models.PROTECT,
        related_name="outages",
        limit_choices_to={"resource_type": Resource.Type.ROOM},
    )
    start_at = models.DateTimeField("เริ่มงดใช้")
    end_at = models.DateTimeField("สิ้นสุดงดใช้")
    reason = models.CharField("เหตุผล", max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="สร้างโดย",
        on_delete=models.PROTECT,
        related_name="created_resource_outages",
    )
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)
    ended_early_at = models.DateTimeField("สิ้นสุดก่อนกำหนดเมื่อ", null=True, blank=True)

    class Meta:
        verbose_name = "ช่วงงดใช้ห้อง"
        verbose_name_plural = "ช่วงงดใช้ห้อง"
        ordering = ["-start_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(end_at__gt=models.F("start_at")), name="outage_end_after_start")
        ]

    def __str__(self):
        return f"{self.resource.code} {self.start_at}–{self.end_at}: {self.reason}"


def room_photo_upload_to(instance: "ResourcePhoto", filename: str) -> str:
    """ตั้งชื่อไฟล์ใหม่เป็น UUID เสมอ (งาน v6-c C2) — กันชื่อไฟล์ซ้ำเขียนทับ (คู่กับ GS_FILE_OVERWRITE=False)
    และเลี่ยงปัญหาชื่อไฟล์ภาษาไทย/อักขระพิเศษที่ผู้ใช้ตั้งเอง ห้ามใช้ชื่อไฟล์เดิมจากผู้ใช้เด็ดขาด
    """
    ext = PurePosixPath(filename).suffix.lower()
    return f"rooms/{uuid.uuid4()}{ext}"


ROOM_PHOTO_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
ROOM_PHOTO_ALLOWED_FORMATS = {"JPEG": "JPEG", "PNG": "PNG", "WEBP": "WebP"}


def validate_room_photo_file(file) -> None:
    """จำกัดชนิดไฟล์ (JPEG/PNG/WebP) และขนาด (≤5MB) — ใช้ Pillow ตรวจชนิดไฟล์จริง
    (ไม่เชื่อแค่นามสกุลไฟล์หรือ content_type ที่ผู้ใช้ส่งมา) ข้อความ error เป็นภาษาไทยเสมอ
    """
    size = getattr(file, "size", None)
    if size is not None and size > ROOM_PHOTO_MAX_SIZE_BYTES:
        raise ValidationError("ขนาดไฟล์รูปต้องไม่เกิน 5MB")

    from PIL import Image, UnidentifiedImageError

    try:
        file.seek(0)
        with Image.open(file) as img:
            img.verify()
            image_format = img.format
    except (UnidentifiedImageError, OSError, ValueError):
        raise ValidationError("ไฟล์นี้ไม่ใช่ไฟล์รูปภาพที่รองรับ กรุณาใช้ไฟล์ชนิด JPEG, PNG หรือ WebP เท่านั้น")
    finally:
        try:
            file.seek(0)
        except Exception:
            pass

    if image_format not in ROOM_PHOTO_ALLOWED_FORMATS:
        raise ValidationError("รองรับเฉพาะไฟล์รูปชนิด JPEG, PNG หรือ WebP เท่านั้น")


class ResourcePhoto(models.Model):
    """รูปประกอบห้อง (งาน v6-c) — เฉพาะห้องเท่านั้น (ไม่ใช่อุปกรณ์ส่วนกลาง)
    ทุกช่องทางสร้าง/แก้ไข/ลบต้องผ่าน resources.services.save_room_photo()/delete_room_photo()
    เท่านั้น (ดูเหตุผลใน docs/v6-plan-antigravity.md งาน C2) — ยกเว้น test ที่พิสูจน์
    constraint ระดับฐานข้อมูลโดยเฉพาะ ซึ่งต้องสร้างตรงผ่าน ORM เพื่อข้าม full_clean()
    """

    resource = models.ForeignKey(
        Resource,
        verbose_name="ห้อง",
        on_delete=models.CASCADE,
        related_name="photos",
        limit_choices_to={"resource_type": Resource.Type.ROOM},
    )
    image = models.ImageField("รูปภาพ", upload_to=room_photo_upload_to, validators=[validate_room_photo_file])
    caption = models.CharField("คำอธิบายภาพ", max_length=200, blank=True)
    order = models.PositiveSmallIntegerField("ลำดับ", default=0)
    is_cover = models.BooleanField("ใช้เป็นรูปหน้าปก", default=False)

    class Meta:
        verbose_name = "รูปห้อง"
        verbose_name_plural = "รูปห้อง"
        ordering = ["-is_cover", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["resource"],
                condition=models.Q(is_cover=True),
                name="unique_cover_photo_per_resource",
                # ข้อความสำรองภาษาไทย เผื่อ validate_constraints() หลุดมาทำงานจริง (ปกติ clean()
                # ด้านล่างจะดักและแปลข้อความไว้ก่อนแล้วเสมอเมื่อสร้าง/แก้ไขผ่าน full_clean())
                violation_error_message="ห้องนี้มีรูปหน้าปกอยู่แล้ว กรุณายกเลิกรูปหน้าปกเดิมก่อน หรือเลือกรูปนี้เป็นปกภายหลัง",
            ),
        ]

    def __str__(self) -> str:
        label = "ปก" if self.is_cover else f"ลำดับ {self.order}"
        code = self.resource.code if self.resource_id else "?"
        return f"รูป{label} — {code}"

    def clean(self):
        super().clean()
        if self.resource_id and self.resource.resource_type != Resource.Type.ROOM:
            raise ValidationError({"resource": "เลือกรูปภาพประกอบได้เฉพาะห้องเท่านั้น ไม่ใช่อุปกรณ์ส่วนกลาง"})
        # แปล error ของ partial unique constraint (unique_cover_photo_per_resource) เป็นข้อความไทยที่อ่านรู้เรื่อง
        # ก่อนถึงชั้นฐานข้อมูล — ตัวบังคับกฎจริงยังอยู่ที่ constraint ด้านบนเสมอ (ดู C2) คีย์ error ไว้ที่ฟิลด์
        # "resource" (ตรงกับ fields=["resource"] ของ constraint) โดยตั้งใจ เพื่อให้ full_clean() เพิ่มชื่อฟิลด์
        # นี้เข้า exclude ก่อนเรียก validate_constraints() ต่อ — กันไม่ให้ Django แปะข้อความ default ซ้ำอีกชั้น
        if self.is_cover and self.resource_id:
            conflict = ResourcePhoto.objects.filter(resource_id=self.resource_id, is_cover=True).exclude(pk=self.pk)
            if conflict.exists():
                raise ValidationError(
                    {"resource": "ห้องนี้มีรูปหน้าปกอยู่แล้ว กรุณายกเลิกรูปหน้าปกเดิมก่อน หรือเลือกรูปนี้เป็นปกภายหลัง"}
                )

"""
การจองและช่วงถือครองทรัพยากร (SRS ข้อ 6, 9, 12)

หัวใจของระบบคือ BookingResource: หนึ่งแถวต่อทรัพยากรที่การจองถือครอง
ช่วง `hold` รวม buffer แล้ว และ ExclusionConstraint ที่ฐานข้อมูลห้ามสองแถวของ
ทรัพยากรเดียวกันซ้อนทับกัน (FR-07/FR-09) ยกเว้นแถวของการจองเดียวกัน (FR-35)
และแถวที่ปลดแล้ว (released_at ไม่ว่าง — FR-10/FR-27)

BookingSeries / BookingAmendment / Preemption จะเพิ่มใน milestone M4–M5
"""
import uuid

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models


class Booking(models.Model):
    class RequestStatus(models.TextChoices):
        DRAFT = "draft", "ร่าง"
        PENDING = "pending", "รออนุมัติ"
        APPROVED = "approved", "อนุมัติ"
        REJECTED = "rejected", "ปฏิเสธ"
        CANCELLED = "cancelled", "ยกเลิก"
        EXPIRED = "expired", "หมดอายุ"

    class UsageStatus(models.TextChoices):
        UPCOMING = "upcoming", "รอใช้งาน"
        USED = "used", "ใช้งานแล้ว"
        NO_SHOW = "no_show", "ไม่มาใช้"
        DISPLACED = "displaced", "ถูกย้าย"
        ROOM_UNAVAILABLE = "room_unavailable", "ห้องใช้งานไม่ได้"

    class Visibility(models.TextChoices):
        NORMAL = "normal", "ปกติ (ทั่วไปเห็น ไม่ว่าง + หน่วย)"
        RESTRICTED = "restricted", "จำกัด (ทั่วไปเห็นแค่ ไม่ว่าง)"
        SENSITIVE = "sensitive", "อ่อนไหว (ล็อกโดย จนท.ความมั่นคงสารสนเทศ)"

    class Purpose(models.TextChoices):
        TEACHING = "teaching", "สอน"
        MEETING = "meeting", "ประชุม"
        TRAINING = "training", "อบรม"
        EXAM = "exam", "สอบ"
        CEREMONY = "ceremony", "พิธี"
        OTHER = "other", "อื่น ๆ"

    # สถานะที่ถือครองเวลา (FR-10)
    HOLDING_STATUSES = (RequestStatus.PENDING, RequestStatus.APPROVED)

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(
        "resources.Resource", verbose_name="ห้อง", on_delete=models.PROTECT, related_name="bookings",
        limit_choices_to={"resource_type": "room"},
    )
    equipment = models.ManyToManyField(
        "resources.Resource",
        verbose_name="อุปกรณ์ส่วนกลางที่ขอ",
        blank=True,
        related_name="bookings_as_equipment",
        limit_choices_to={"resource_type": "equipment"},
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="ผู้จอง", on_delete=models.PROTECT, related_name="bookings"
    )
    unit = models.ForeignKey("accounts.Unit", verbose_name="หน่วยงานผู้ขอ", on_delete=models.PROTECT, related_name="bookings")
    responsible_name = models.CharField("ผู้รับผิดชอบ (ชื่อ-ตำแหน่ง)", max_length=200)
    responsible_phone = models.CharField("โทรศัพท์ผู้รับผิดชอบ", max_length=30)

    title = models.CharField("ชื่อกิจกรรม / วิชา", max_length=200)
    purpose = models.CharField("ประเภทการใช้งาน", max_length=20, choices=Purpose.choices, default=Purpose.TEACHING)
    start_at = models.DateTimeField("เริ่ม")
    end_at = models.DateTimeField("สิ้นสุด")
    attendees = models.PositiveIntegerField("จำนวนผู้เข้าร่วม", default=1)
    attendee_level = models.CharField("ระดับ/ชั้นผู้เข้าร่วม", max_length=100, blank=True)
    layout = models.CharField("รูปแบบจัดโต๊ะ", max_length=100, blank=True)
    fixed_equipment_needed = models.TextField("อุปกรณ์ประจำห้องที่ต้องใช้", blank=True)
    has_external_attendees = models.BooleanField("มีผู้เข้าร่วมจากภายนอก", default=False)
    external_attendees_note = models.CharField("จำนวน/หน่วยของผู้เข้าร่วมภายนอก", max_length=200, blank=True)
    visibility = models.CharField("ระดับการมองเห็น", max_length=20, choices=Visibility.choices, default=Visibility.NORMAL)
    note = models.TextField("หมายเหตุ", blank=True)

    request_status = models.CharField("สถานะคำขอ", max_length=20, choices=RequestStatus.choices, default=RequestStatus.DRAFT)
    usage_status = models.CharField("สถานะการใช้งาน", max_length=20, choices=UsageStatus.choices, default=UsageStatus.UPCOMING)
    is_urgent = models.BooleanField("คำขอเร่งด่วน", default=False, help_text="ตั้งโดยระบบตาม FR-23")
    revision = models.PositiveIntegerField("รุ่นข้อมูล", default=1, help_text="เพิ่มทุกครั้งที่แก้ไข ใช้กัน amendment ทับข้อมูลเก่า")

    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)
    updated_at = models.DateTimeField("แก้ไขล่าสุด", auto_now=True)
    submitted_at = models.DateTimeField("ส่งคำขอเมื่อ", null=True, blank=True)
    sla_escalated_at = models.DateTimeField("เปิดสิทธิ์ผู้อนุมัติสำรองเมื่อ", null=True, blank=True)
    decision_reason = models.TextField("เหตุผลการพิจารณาล่าสุด", blank=True)

    class Meta:
        verbose_name = "การจอง"
        verbose_name_plural = "การจอง"
        ordering = ["-start_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(end_at__gt=models.F("start_at")), name="booking_end_after_start"),
        ]
        indexes = [
            models.Index(fields=["room", "start_at"]),
            models.Index(fields=["requester", "start_at"]),
            models.Index(fields=["request_status"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} — {self.room.code} {self.start_at:%Y-%m-%d %H:%M}"

    @property
    def is_holding(self) -> bool:
        return self.request_status in self.HOLDING_STATUSES


class BookingResource(models.Model):
    """
    ช่วงถือครองทรัพยากร — หนึ่งแถวต่อ (การจอง, ทรัพยากร)
    `hold` = [start - buffer_before, end + buffer_after) รวม buffer แล้ว (FR-07)
    `amendment` จะถูกเพิ่มใน M5 (แถวถือครองชั่วคราวของคำขอแก้ไข)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, verbose_name="การจอง", on_delete=models.CASCADE, related_name="holds")
    resource = models.ForeignKey("resources.Resource", verbose_name="ทรัพยากร", on_delete=models.PROTECT, related_name="holds")
    hold = DateTimeRangeField("ช่วงถือครอง (รวม buffer)")
    released_at = models.DateTimeField("ปลดเมื่อ", null=True, blank=True)

    class Meta:
        verbose_name = "ช่วงถือครองทรัพยากร"
        verbose_name_plural = "ช่วงถือครองทรัพยากร"
        constraints = [
            # FR-09 / FR-35: ทรัพยากรเดียวกัน ช่วงซ้อนกัน การจองต่างกัน และยังไม่ปลด → ห้าม
            ExclusionConstraint(
                name="excl_overlapping_holds",
                index_type="GIST",
                expressions=[
                    ("resource", RangeOperators.EQUAL),
                    ("booking", RangeOperators.NOT_EQUAL),
                    ("hold", RangeOperators.OVERLAPS),
                ],
                condition=models.Q(released_at__isnull=True),
            ),
            # P1.2: ห้ามช่วงว่าง และห้ามทรัพยากรซ้ำในการจองเดียวกันขณะยังถือครอง
            models.CheckConstraint(condition=~models.Q(hold__isempty=True), name="hold_not_empty"),
            models.UniqueConstraint(
                fields=["booking", "resource"], condition=models.Q(released_at__isnull=True), name="uniq_active_hold_per_booking_resource"
            ),
        ]

    def __str__(self) -> str:
        state = "ปลดแล้ว" if self.released_at else "ถือครอง"
        return f"{self.resource.code} {self.hold.lower:%Y-%m-%d %H:%M}–{self.hold.upper:%H:%M} ({state})"

import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from resources.models import Resource

from .phone_utils import normalize_phone


class CourseLodgingCohort(models.Model):
    """รอบการเปิดให้นักเรียนหลักสูตรจองห้องพักด้วยตนเองผ่านลิงก์"""

    class AllocationStatus(models.TextChoices):
        ALLOCATED = "allocated", "จัดสรรห้องพัก (สงวนห้อง)"
        RELEASED = "released", "ปลดการสงวนห้อง (ยังไม่จัดสรร/เสร็จสิ้น)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField("ชื่อหลักสูตร/รุ่น", max_length=200, help_text="เช่น หลักสูตรชั้นนายร้อย เหล่า ส. รุ่นที่ 70")
    slug = models.SlugField("รหัสลิงก์ (URL slug)", max_length=50, unique=True, help_text="ใช้ในลิงก์แชร์ เช่น nr-70")
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ผู้กำกับหลักสูตร",
        on_delete=models.PROTECT,
        related_name="managed_lodging_cohorts",
    )
    unit = models.ForeignKey(
        "accounts.Unit",
        verbose_name="หน่วยจัดการศึกษา",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    check_in_date = models.DateField("วันที่เริ่มเข้าพัก")
    check_out_date = models.DateField("วันที่สิ้นสุดการเข้าพัก")
    rooms = models.ManyToManyField(
        Resource,
        verbose_name="ห้องพักที่เปิดให้จอง",
        related_name="course_cohorts",
        limit_choices_to={"resource_type": Resource.Type.ROOM, "room_category": Resource.Category.LODGING},
    )
    beds_per_room = models.PositiveIntegerField("จำนวนคน/เตียงต่อห้อง", default=4)
    allocation_status = models.CharField(
        "สถานะการจัดสรรห้องพัก",
        max_length=20,
        choices=AllocationStatus.choices,
        default=AllocationStatus.RELEASED,
    )
    is_active = models.BooleanField("เปิดรับการจอง", default=False)
    note = models.TextField("คำชี้แจง/ข้อปฏิบัติในการเข้าพัก", blank=True)
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)

    class Meta:
        verbose_name = "รอบจองที่พักหลักสูตร"
        verbose_name_plural = "รอบจองที่พักหลักสูตร"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(allocation_status="released", is_active=True),
                name="check_released_cohort_cannot_be_active",
            ),
            models.CheckConstraint(
                condition=models.Q(check_out_date__gte=models.F("check_in_date")),
                name="check_cohort_checkout_after_checkin",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.slug})"

    def get_absolute_url(self):
        return reverse("bookings:lodging_portal", args=[self.slug])

    def total_capacity(self):
        return self.rooms.count() * self.beds_per_room

    def booked_count(self):
        return self.students.count()

    def remaining_slots(self):
        return max(0, self.total_capacity() - self.booked_count())

    def clean(self):
        super().clean()
        errors = {}
        if self.check_in_date and self.check_out_date and self.check_out_date < self.check_in_date:
            errors["check_out_date"] = "วันที่สิ้นสุดการเข้าพักต้องไม่ก่อนวันที่เริ่มเข้าพัก"
        if self.beds_per_room is not None and self.beds_per_room < 1:
            errors["beds_per_room"] = "จำนวนเตียงต่อห้องต้องอย่างน้อย 1"
        if self.allocation_status == self.AllocationStatus.RELEASED and self.is_active:
            errors["is_active"] = "รอบที่ปลดการสงวนห้องแล้วต้องไม่เปิดรับจอง"
        if errors:
            raise ValidationError(errors)


class CourseStudentLodging(models.Model):
    """ข้อมูลการจองห้องพักของนักเรียนรายบุคคล (1 คนต่อ 1 เตียงในห้อง)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cohort = models.ForeignKey(
        CourseLodgingCohort,
        verbose_name="รอบหลักสูตร",
        on_delete=models.CASCADE,
        related_name="students",
    )
    room = models.ForeignKey(
        Resource,
        verbose_name="ห้องพัก",
        on_delete=models.PROTECT,
        related_name="student_lodgings",
    )
    bed_number = models.PositiveSmallIntegerField("เตียงที่", default=1)
    rank = models.CharField("ยศ", max_length=50)
    full_name = models.CharField("ชื่อ-นามสกุล", max_length=150)
    origin_unit = models.CharField("หน่วยต้นสังกัด", max_length=150)
    phone = models.CharField("เบอร์โทรศัพท์", max_length=30)
    note = models.CharField("หมายเหตุเพิ่มเติม", max_length=200, blank=True)
    booked_at = models.DateTimeField("เวลาที่จอง", auto_now_add=True)

    class Meta:
        verbose_name = "การจองห้องพักนักเรียน"
        verbose_name_plural = "การจองห้องพักนักเรียน"
        ordering = ["room__code", "bed_number"]
        constraints = [
            # ห้ามเตียงเดียวกันในห้องเดียวกันถูกจองซ้ำในหลักสูตรเดียวกัน
            models.UniqueConstraint(
                fields=["cohort", "room", "bed_number"],
                name="unique_cohort_room_bed",
            ),
            # ห้ามเบอร์โทรเดียวกันจองซ้ำในหลักสูตรเดียวกัน
            models.UniqueConstraint(
                fields=["cohort", "phone"],
                name="unique_cohort_student_phone",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.cohort_id and self.room_id:
            try:
                cohort = CourseLodgingCohort.objects.get(pk=self.cohort_id)
            except CourseLodgingCohort.DoesNotExist:
                errors["cohort"] = "ไม่พบรอบหลักสูตรที่เลือก"
                cohort = None
            if cohort is None:
                raise ValidationError(errors)
            if not cohort.rooms.filter(pk=self.room_id).exists():
                errors["room"] = "ห้องนี้ไม่ได้อยู่ในรายการห้องของรอบหลักสูตร"
            if self.bed_number is not None and not (1 <= self.bed_number <= cohort.beds_per_room):
                errors["bed_number"] = f"หมายเลขเตียงต้องอยู่ระหว่าง 1 ถึง {cohort.beds_per_room}"
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        if not self.phone:
            raise ValidationError("กรุณาระบุเบอร์โทรศัพท์ที่ถูกต้อง")
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.rank} {self.full_name} ({self.room.code} เตียง {self.bed_number})"

import uuid
from django.conf import settings
from django.db import models
from django.urls import reverse
from resources.models import Resource


class CourseLodgingCohort(models.Model):
    """รอบการเปิดให้นักเรียนหลักสูตรจองห้องพักด้วยตนเองผ่านลิงก์"""

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
    is_active = models.BooleanField("เปิดรับการจอง", default=True)
    note = models.TextField("คำชี้แจง/ข้อปฏิบัติในการเข้าพัก", blank=True)
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)

    class Meta:
        verbose_name = "รอบจองที่พักหลักสูตร"
        verbose_name_plural = "รอบจองที่พักหลักสูตร"
        ordering = ["-created_at"]

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

    def __str__(self):
        return f"{self.rank} {self.full_name} ({self.room.code} เตียง {self.bed_number})"

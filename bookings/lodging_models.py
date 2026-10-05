import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from resources.models import Resource

from .phone_utils import normalize_phone


class CourseLodgingCohort(models.Model):
    """รอบการเปิดให้นักเรียนหลักสูตรจองห้องพักด้วยตนเองผ่านลิงก์"""

    class AllocationStatus(models.TextChoices):
        ALLOCATED = "allocated", "จัดสรรห้องพัก (สงวนห้อง)"
        RELEASED = "released", "ปลดการสงวนห้อง (ยังไม่จัดสรร/เสร็จสิ้น)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_run = models.OneToOneField(
        "bookings.CourseRun",
        verbose_name="รุ่นหลักสูตรกลาง",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="lodging_cohort",
    )
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
    is_active = models.BooleanField("เปิดใช้การจองด้วยตนเอง", default=False)
    open_enrollment = models.BooleanField(
        "เข้าสู่ระบบด้วยอีเมลโรงเรียนแล้วจองได้ทันที",
        default=True,
        help_text="ปิดเมื่อต้องการให้จองได้เฉพาะอีเมลที่เจ้าหน้าที่ใส่ในรายชื่อรุ่นไว้ก่อน",
    )
    booking_open_at = models.DateTimeField("เปิดรับจองเมื่อ", null=True, blank=True)
    booking_close_at = models.DateTimeField("ปิดรับจองเมื่อ", null=True, blank=True)
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
            models.CheckConstraint(
                condition=(
                    models.Q(booking_open_at__isnull=True)
                    | models.Q(booking_close_at__isnull=True)
                    | models.Q(booking_close_at__gte=models.F("booking_open_at"))
                ),
                name="check_cohort_booking_window_order",
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
        if self.booking_open_at and self.booking_close_at and self.booking_close_at < self.booking_open_at:
            errors["booking_close_at"] = "เวลาปิดรับจองต้องไม่ก่อนเวลาเปิดรับจอง"
        if errors:
            raise ValidationError(errors)


class CourseStudentLodging(models.Model):
    """ข้อมูลการจองห้องพักของนักเรียนรายบุคคล (1 คนต่อ 1 เตียงในห้อง)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="เจ้าของบัญชี", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="course_student_lodgings",
    )
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
    lodging_rate = models.ForeignKey("bookings.LodgingRate", verbose_name="อัตราค่าที่พักที่เจ้าหน้าที่เลือก",
        null=True, blank=True, on_delete=models.PROTECT, related_name="students")
    booked_at = models.DateTimeField("เวลาที่จอง", auto_now_add=True)
    checked_in_at = models.DateTimeField("เวลารายงานตัว", null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ผู้ยืนยันรายงานตัว",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="checked_in_lodging_students",
    )

    class Meta:
        verbose_name = "การจองห้องพักนักเรียน"
        verbose_name_plural = "การจองห้องพักนักเรียน"
        ordering = ["room__code", "bed_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["cohort", "room", "bed_number"],
                name="unique_cohort_room_bed",
            ),
            models.UniqueConstraint(
                fields=["cohort", "phone"],
                name="unique_cohort_student_phone",
            ),
            models.UniqueConstraint(
                fields=["cohort", "user"], condition=models.Q(user__isnull=False),
                name="unique_cohort_student_user",
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
            room = Resource.objects.filter(pk=self.room_id).only("resource_type", "room_category").first()
            if room is None:
                errors["room"] = "ไม่พบห้องพักที่เลือก"
            elif room.resource_type != Resource.Type.ROOM or room.room_category != Resource.Category.LODGING:
                errors["room"] = "เลือกได้เฉพาะทรัพยากรประเภทห้องในหมวดห้องพัก"
            elif not cohort.rooms.filter(pk=self.room_id).exists():
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


class CourseStudentEnrollment(models.Model):
    """รายชื่ออีเมลที่ผู้จัดหลักสูตรยืนยัน; QR หรือโดเมนอีเมลไม่ใช่หลักฐานสมาชิก."""

    cohort = models.ForeignKey(CourseLodgingCohort, on_delete=models.CASCADE,
                              related_name="enrollments", verbose_name="รุ่นหลักสูตร")
    email = models.EmailField("อีเมลโรงเรียน")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL, related_name="student_enrollments",
                             verbose_name="บัญชีที่ยืนยันแล้ว")
    rank = models.CharField("ยศ", max_length=50, blank=True)
    origin_unit = models.CharField("หน่วยต้นสังกัด", max_length=150, blank=True)
    phone = models.CharField("เบอร์โทรศัพท์", max_length=30, blank=True)
    is_active = models.BooleanField("อนุญาตให้จองเตียง", default=True)

    class Meta:
        verbose_name = "รายชื่อนักเรียนที่มีสิทธิ์จองเตียง"
        verbose_name_plural = "รายชื่อนักเรียนที่มีสิทธิ์จองเตียง"
        constraints = [models.UniqueConstraint(fields=["cohort", "email"],
                                              name="unique_cohort_enrollment_email")]

    def clean(self):
        from accounts.models import validate_allowed_email_domain
        self.email = (self.email or "").strip().lower()
        validate_allowed_email_domain(self.email)
        self.phone = normalize_phone(self.phone) if self.phone else ""
        if self.user_id and self.user.email.lower() != self.email:
            raise ValidationError("อีเมลต้องตรงกับบัญชีของนักเรียน")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cohort.title} / {self.email}"


class CourseLodgingAccess(models.Model):
    """Opaque self-service capability for managing one active course lodging reservation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(
        CourseStudentLodging,
        verbose_name="การจองที่พักนักเรียน",
        on_delete=models.CASCADE,
        related_name="self_service_access",
    )
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)

    class Meta:
        verbose_name = "ลิงก์จัดการการจองที่พักนักเรียน"
        verbose_name_plural = "ลิงก์จัดการการจองที่พักนักเรียน"

    def __str__(self):
        return f"{self.student_id} / {self.pk}"


class CourseLodgingRelease(models.Model):
    """Immutable operational history for a reservation removed from active bed inventory."""

    class Outcome(models.TextChoices):
        CANCELLED = "cancelled", "ยกเลิก"
        NO_SHOW = "no_show", "ไม่มารายงานตัว"
        CHECKED_OUT = "checked_out", "ออกจากที่พัก"

    class Channel(models.TextChoices):
        SELF_SERVICE = "self_service", "นักเรียนยกเลิกเอง"
        STAFF = "staff", "เจ้าหน้าที่ดำเนินการ"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    original_student_id = models.UUIDField("รหัสการจองเดิม", unique=True)
    cohort = models.ForeignKey(
        CourseLodgingCohort,
        verbose_name="รอบหลักสูตร",
        on_delete=models.PROTECT,
        related_name="releases",
    )
    room = models.ForeignKey(
        Resource,
        verbose_name="ห้องพักเดิม",
        on_delete=models.PROTECT,
        related_name="course_lodging_releases",
    )
    bed_number = models.PositiveSmallIntegerField("เตียงเดิม")
    rank = models.CharField("ยศ", max_length=50)
    full_name = models.CharField("ชื่อ-นามสกุล", max_length=150)
    origin_unit = models.CharField("หน่วยต้นสังกัด", max_length=150)
    phone = models.CharField("เบอร์โทรศัพท์", max_length=30)
    note = models.CharField("หมายเหตุเดิม", max_length=200, blank=True)
    booked_at = models.DateTimeField("เวลาที่จองเดิม")
    checked_in_at = models.DateTimeField("เวลารายงานตัวเดิม", null=True, blank=True)
    checked_in_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ผู้ยืนยันรายงานตัวเดิม",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="checked_out_course_lodgings",
    )
    outcome = models.CharField("ผลการปล่อยเตียง", max_length=20, choices=Outcome.choices)
    channel = models.CharField("ช่องทาง", max_length=20, choices=Channel.choices)
    reason = models.CharField("เหตุผล", max_length=300, blank=True)
    released_at = models.DateTimeField("ปล่อยเตียงเมื่อ", auto_now_add=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ผู้ดำเนินการ",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="released_course_lodgings",
    )

    class Meta:
        verbose_name = "ประวัติการปล่อยเตียงนักเรียน"
        verbose_name_plural = "ประวัติการปล่อยเตียงนักเรียน"
        ordering = ["-released_at"]
        indexes = [models.Index(fields=["cohort", "outcome", "released_at"])]

    def __str__(self):
        return f"{self.get_outcome_display()} {self.full_name} / {self.room.code}-{self.bed_number}"


class PublicLodgingAccess(models.Model):
    """Opaque public status link for a general lodging request backed by Booking Core."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.OneToOneField(
        "bookings.Booking",
        verbose_name="คำขอจองที่พัก",
        on_delete=models.CASCADE,
        related_name="public_lodging_access",
    )
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)

    class Meta:
        verbose_name = "ลิงก์ติดตามคำขอที่พักบุคคลทั่วไป"
        verbose_name_plural = "ลิงก์ติดตามคำขอที่พักบุคคลทั่วไป"

    def __str__(self):
        return f"{self.booking_id} / {self.pk}"


class LodgingRate(models.Model):
    class Basis(models.TextChoices):
        PERSON = "person", "ต่อคน"
        ROOM = "room", "ต่อห้อง"

    category = models.CharField("ประเภทผู้พัก", max_length=100)
    cooling = models.CharField("แอร์/พัดลม", max_length=8, choices=Resource.Cooling.choices)
    daily_price = models.DecimalField("ราคาต่อวัน", max_digits=10, decimal_places=2)
    monthly_price = models.DecimalField("ราคาต่อเดือน (แสดงเพื่อเปรียบเทียบ)", max_digits=10, decimal_places=2)
    effective_from = models.DateField("มีผลตั้งแต่")
    basis = models.CharField("หน่วยคิดเงิน", max_length=8, choices=Basis.choices, default=Basis.PERSON)

    class Meta:
        verbose_name = "อัตราค่าที่พัก"
        verbose_name_plural = "อัตราค่าที่พัก"
        ordering = ["category", "cooling", "-effective_from"]
        constraints = [
            models.UniqueConstraint(fields=["category", "cooling", "effective_from"], name="unique_lodging_rate_date"),
            models.CheckConstraint(condition=models.Q(daily_price__gte=0, monthly_price__gte=0), name="nonnegative_lodging_rate"),
        ]

    def clean(self):
        super().clean()
        if self.daily_price is not None and self.daily_price < 0 or self.monthly_price is not None and self.monthly_price < 0:
            raise ValidationError("ราคาค่าที่พักต้องไม่ติดลบ")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.category} · {self.get_cooling_display()} · {self.daily_price} บาท/{self.get_basis_display()}"


class LodgingMeterReading(models.Model):
    room = models.ForeignKey(Resource, verbose_name="ห้องแอร์", on_delete=models.PROTECT, related_name="lodging_meters")
    check_in_date = models.DateField("วันเข้าพัก")
    check_out_date = models.DateField("วันออก")
    meter_in = models.DecimalField("เลขมิเตอร์เข้า", max_digits=12, decimal_places=3)
    meter_out = models.DecimalField("เลขมิเตอร์ออก", max_digits=12, decimal_places=3, null=True, blank=True)
    unit_price = models.DecimalField("ราคาค่าไฟต่อหน่วย", max_digits=10, decimal_places=4, null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="ผู้บันทึก", on_delete=models.PROTECT)
    recorded_at = models.DateTimeField("เวลาบันทึกล่าสุด", auto_now=True)

    class Meta:
        verbose_name = "มิเตอร์ไฟห้องพัก"
        verbose_name_plural = "มิเตอร์ไฟห้องพัก"
        constraints = [
            models.UniqueConstraint(fields=["room", "check_in_date", "check_out_date"], name="unique_room_stay_meter"),
            models.CheckConstraint(condition=models.Q(check_out_date__gte=models.F("check_in_date")), name="meter_stay_dates_valid"),
            models.CheckConstraint(condition=models.Q(meter_in__gte=0) & (models.Q(meter_out__isnull=True) | models.Q(meter_out__gte=models.F("meter_in"))), name="meter_values_valid"),
            models.CheckConstraint(condition=models.Q(unit_price__isnull=True) | models.Q(unit_price__gte=0), name="meter_price_nonnegative"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.pk:
            original_recorded_by_id = (
                type(self).objects.filter(pk=self.pk)
                .values_list("recorded_by_id", flat=True)
                .first()
            )
            if original_recorded_by_id and self.recorded_by_id != original_recorded_by_id:
                errors["recorded_by"] = "ไม่อนุญาตให้แก้ไขผู้บันทึกเดิม"
        if self.room_id and (self.room.room_category != Resource.Category.LODGING or self.room.lodging_cooling != Resource.Cooling.AIR):
            errors["room"] = "บันทึกมิเตอร์ได้เฉพาะห้องพักประเภทแอร์"
        if self.check_in_date and self.check_out_date and self.check_out_date < self.check_in_date:
            errors["check_out_date"] = "วันออกต้องไม่อยู่ก่อนวันเข้าพัก"
        if self.room_id and self.check_in_date and self.check_out_date:
            from .models import Booking
            if self.pk:
                existing = (
                    type(self).objects.filter(pk=self.pk)
                    .values("room_id", "check_in_date", "check_out_date")
                    .first()
                )
                if (
                    existing
                    and existing["room_id"] == self.room_id
                    and existing["check_in_date"] == self.check_in_date
                    and existing["check_out_date"] == self.check_out_date
                ):
                    cohort_stay = True
                else:
                    cohort_stay = CourseLodgingCohort.objects.filter(
                        rooms=self.room,
                        check_in_date=self.check_in_date,
                        check_out_date=self.check_out_date,
                    ).exists()
            else:
                cohort_stay = CourseLodgingCohort.objects.filter(
                    rooms=self.room,
                    check_in_date=self.check_in_date,
                    check_out_date=self.check_out_date,
                ).exists()

            guest_stay = Booking.objects.filter(
                room=self.room,
                request_status="approved",
                public_lodging_access__isnull=False,
                start_at__date=self.check_in_date,
                end_at__date=self.check_out_date,
            ).exists()
            if not cohort_stay and not guest_stay:
                errors["check_in_date"] = "ช่วงมิเตอร์ต้องตรงกับช่วงเข้าพักที่จัดสรรหรืออนุมัติแล้วของห้องนี้"
        if self.meter_in is not None and self.meter_in < 0:
            errors["meter_in"] = "เลขมิเตอร์ต้องไม่ติดลบ"
        if self.meter_out is not None:
            if self.meter_in is not None and self.meter_out < self.meter_in:
                errors["meter_out"] = "เลขมิเตอร์ออกต้องไม่น้อยกว่าเลขมิเตอร์เข้า"
            if self.unit_price is None:
                errors["unit_price"] = "กรุณากรอกราคาค่าไฟต่อหน่วยก่อนสรุปยอด"
        if self.unit_price is not None and self.unit_price < 0:
            errors["unit_price"] = "ราคาค่าไฟต่อหน่วยต้องไม่ติดลบ"
        if errors:
            raise ValidationError(errors)

    @transaction.atomic
    def save(self, *args, **kwargs):
        from audit.context import current_actor
        from audit.services import audit, model_snapshot
        previous = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        self.full_clean()
        result = super().save(*args, **kwargs)
        audit(current_actor() or self.recorded_by, "bookings.lodgingmeterreading", self.pk, "lodging_meter_saved",
              before=model_snapshot(previous) if previous else None, after=model_snapshot(self))
        return result


class PublicLodgingThrottle(models.Model):
    """Fixed-window counters for anonymous public lodging submissions; keys are HMAC hashes."""

    class Scope(models.TextChoices):
        PHONE = "phone", "เบอร์โทรศัพท์"
        CLIENT = "client", "เบราว์เซอร์/เซสชัน"

    scope = models.CharField("ขอบเขต", max_length=16, choices=Scope.choices)
    key_hash = models.CharField("รหัสแฮช", max_length=64)
    window_start = models.DateTimeField("เริ่มช่วงเวลา")
    count = models.PositiveSmallIntegerField("จำนวนครั้ง", default=0)

    class Meta:
        verbose_name = "ตัวนับป้องกันคำขอที่พักซ้ำถี่"
        verbose_name_plural = "ตัวนับป้องกันคำขอที่พักซ้ำถี่"
        constraints = [
            models.UniqueConstraint(
                fields=["scope", "key_hash", "window_start"],
                name="unique_public_lodging_throttle_window",
            )
        ]
        indexes = [models.Index(fields=["window_start"])]

    def __str__(self):
        return f"{self.scope}:{self.window_start.isoformat()}={self.count}"

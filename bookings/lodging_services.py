"""กฎธุรกิจส่วนกลางของการจัดสรรที่พักหลักสูตร.

การแก้ไขห้อง วันที่ สถานะ และจำนวนเตียงต้องผ่าน service นี้ เพื่อให้ทุกช่องทาง
(หน้าจัดการ, Django admin และคำสั่ง seed) ใช้ transaction และกติกาชุดเดียวกัน.
"""

from datetime import date, datetime, time, timedelta
from typing import Sequence
from urllib.parse import urlencode

from django.conf import settings
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import audit
from resources.models import Resource

from .lodging_models import CourseLodgingCohort, CourseStudentLodging
from .models import BookingResource
from .phone_utils import normalize_phone  # noqa: F401 (re-exported for bookings.lodging_views)


def cohort_hold_range(check_in_date: date, check_out_date: date) -> DateTimeTZRange:
    """ช่วงสงวนห้องแบบ half-open ตั้งแต่เที่ยงคืนวันเข้า ถึงเที่ยงคืนถัดจากวันออก"""
    zone = timezone.get_current_timezone()
    lower = timezone.make_aware(datetime.combine(check_in_date, time.min), zone)
    upper = timezone.make_aware(
        datetime.combine(check_out_date + timedelta(days=1), time.min), zone
    )
    return DateTimeTZRange(lower, upper, "[)")


def cohort_conflict_for_resource(resource: Resource, start_at: datetime, end_at: datetime):
    """คืนรุ่นที่สงวนห้องชนกับช่วงเวลานี้ หรือ None."""
    if resource.room_category != Resource.Category.LODGING:
        return None
    local_start = timezone.localtime(start_at).date()
    local_end = timezone.localtime(end_at - timedelta(microseconds=1)).date()
    return (
        CourseLodgingCohort.objects.filter(
            allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
            rooms=resource,
            check_in_date__lte=local_end,
            check_out_date__gte=local_start,
        )
        .order_by("pk")
        .first()
    )


def can_create_cohort(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "is_staff", False)
            or getattr(user, "unit_id", None)
        )
    )


def can_manage_cohort(user, cohort: CourseLodgingCohort) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or cohort.supervisor_id == getattr(user, "pk", None)
    )


def generate_cohort_qr_svg(url: str) -> bytes:
    """สร้าง QR SVG จาก URL โดยคืน bytes พร้อมส่งเป็น HTTP response ได้ทันที"""
    import qrcode
    from qrcode.image.svg import SvgPathImage

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(image_factory=SvgPathImage).to_string()


def generate_line_share_url(title: str, url: str) -> str:
    return "https://line.me/R/share?" + urlencode({"text": f"{title}\n{url}"})


def get_canonical_public_url(request, path: str) -> str:
    path = path if path.startswith("/") else f"/{path}"
    base_url = getattr(settings, "PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base_url:
        return f"{base_url}{path}"
    return request.build_absolute_uri(path)


def _actor_is_superuser(actor) -> bool:
    return bool(
        getattr(actor, "is_authenticated", False)
        and getattr(actor, "is_superuser", False)
    )


@transaction.atomic
def update_cohort_allocation(
    cohort: CourseLodgingCohort,
    rooms: Sequence[Resource],
    check_in_date: date,
    check_out_date: date,
    allocation_status: str,
    is_active: bool,
    beds_per_room: int,
    supervisor=None,
    title: str | None = None,
    note: str | None = None,
    actor=None,
    force_release: bool = False,
    release_reason: str = "",
) -> CourseLodgingCohort:
    """บันทึกการจัดสรรห้องแบบ transaction พร้อมล็อกทรัพยากรตามลำดับ PK."""
    creating = cohort._state.adding
    if creating:
        locked_cohort = cohort
        current_room_pks = set()
    else:
        locked_cohort = CourseLodgingCohort.objects.select_for_update().get(pk=cohort.pk)
        current_room_pks = set(locked_cohort.rooms.values_list("pk", flat=True))

    if actor is not None:
        allowed = can_create_cohort(actor) if creating else can_manage_cohort(actor, locked_cohort)
        if not allowed:
            raise PermissionDenied("คุณไม่มีสิทธิ์จัดการรอบที่พักนี้")

    if force_release and not _actor_is_superuser(actor):
        raise PermissionDenied("เฉพาะผู้ดูแลระบบสูงสุดเท่านั้นที่ใช้การปลดการสงวนแบบบังคับได้")
    if force_release and not (release_reason or "").strip():
        raise ValidationError("กรุณาระบุเหตุผลในการปลดการสงวนห้องพักหรือร่นวันสิ้นสุดก่อนกำหนด")

    target_rooms = list(rooms)
    target_room_pks = {room.pk for room in target_rooms if getattr(room, "pk", None)}
    all_room_pks = sorted(target_room_pks | current_room_pks)
    locked_resources = list(
        Resource.objects.select_for_update().filter(pk__in=all_room_pks).order_by("pk")
    )
    resources_by_pk = {resource.pk: resource for resource in locked_resources}
    if not target_room_pks.issubset(resources_by_pk):
        raise ValidationError("มีห้องพักที่เลือกไม่พบในระบบ")
    target_resources = [resources_by_pk[pk] for pk in sorted(target_room_pks)]

    # ตรวจจากค่าเดิมในแถวที่ล็อกไว้ก่อนตรวจ scalar ใหม่ เพื่อปิดช่องโหว่
    # ที่พยายามร่นวันสิ้นสุดพร้อมเปลี่ยนสถานะในคำขอเดียวกัน
    today = timezone.localdate()
    was_allocated = (
        not creating
        and locked_cohort.allocation_status == CourseLodgingCohort.AllocationStatus.ALLOCATED
    )
    has_students = not creating and locked_cohort.students.exists()
    original_not_ended = was_allocated and locked_cohort.check_out_date >= today
    releasing = allocation_status == CourseLodgingCohort.AllocationStatus.RELEASED
    backdating_end = (
        allocation_status == CourseLodgingCohort.AllocationStatus.ALLOCATED
        and check_out_date < today
    )
    if original_not_ended and has_students and (releasing or backdating_end) and not force_release:
        raise ValidationError("ไม่สามารถปลดการสงวนห้องหรือร่นวันสิ้นสุดก่อนกำหนดได้ขณะที่มีนักเรียนจองอยู่")

    if allocation_status not in CourseLodgingCohort.AllocationStatus.values:
        raise ValidationError("สถานะการจัดสรรห้องพักไม่ถูกต้อง")
    if check_out_date < check_in_date:
        raise ValidationError({"check_out_date": "วันที่สิ้นสุดการเข้าพักต้องไม่ก่อนวันที่เริ่มเข้าพัก"})
    if beds_per_room < 1:
        raise ValidationError({"beds_per_room": "จำนวนเตียงต่อห้องต้องอย่างน้อย 1"})
    if allocation_status == CourseLodgingCohort.AllocationStatus.RELEASED and is_active:
        raise ValidationError("รอบที่ปลดการสงวนห้องแล้วต้องไม่เปิดรับจอง")
    if allocation_status == CourseLodgingCohort.AllocationStatus.ALLOCATED and not target_resources:
        raise ValidationError("สถานะจัดสรรห้องพักต้องมีห้องอย่างน้อย 1 ห้อง")
    if any(
        resource.resource_type != Resource.Type.ROOM
        or resource.room_category != Resource.Category.LODGING
        or resource.status != Resource.Status.ACTIVE
        for resource in target_resources
    ):
        raise ValidationError("เลือกได้เฉพาะห้องพักที่เปิดใช้งานอยู่")

    student_room_pks = set()
    max_booked_bed = 0
    if not creating:
        student_room_pks = set(locked_cohort.students.values_list("room_id", flat=True))
        max_booked_bed = max(
            locked_cohort.students.values_list("bed_number", flat=True),
            default=0,
        )
    if not student_room_pks.issubset(target_room_pks):
        raise ValidationError("ไม่สามารถถอดห้องที่มีนักเรียนจองอยู่ในรุ่นนี้")
    if beds_per_room < max_booked_bed:
        raise ValidationError(f"ไม่สามารถลดจำนวนเตียงต่ำกว่าเตียงที่จองแล้ว (เตียง {max_booked_bed})")

    if allocation_status == CourseLodgingCohort.AllocationStatus.ALLOCATED:
        hold = cohort_hold_range(check_in_date, check_out_date)
        other_cohorts = (
            CourseLodgingCohort.objects.filter(
                allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
                rooms__in=target_resources,
                check_in_date__lte=check_out_date,
                check_out_date__gte=check_in_date,
            )
            .exclude(pk=None if creating else locked_cohort.pk)
            .distinct()
        )
        if other_cohorts.exists():
            raise ValidationError("ห้องพักชนกับรอบหลักสูตรที่จัดสรรไว้แล้ว")

        if BookingResource.objects.filter(
            resource__in=target_resources,
            released_at__isnull=True,
            hold__overlap=hold,
        ).exists():
            raise ValidationError("ห้องพักชนกับการจองห้องปกติที่ยังถือครองอยู่")

    before = {
        "allocation_status": getattr(locked_cohort, "allocation_status", None),
        "is_active": getattr(locked_cohort, "is_active", None),
        "check_in_date": getattr(locked_cohort, "check_in_date", None),
        "check_out_date": getattr(locked_cohort, "check_out_date", None),
        "rooms": sorted(current_room_pks),
    }
    locked_cohort.check_in_date = check_in_date
    locked_cohort.check_out_date = check_out_date
    locked_cohort.allocation_status = allocation_status
    locked_cohort.is_active = is_active
    locked_cohort.beds_per_room = beds_per_room
    if supervisor is not None:
        locked_cohort.supervisor = supervisor
    if title is not None:
        locked_cohort.title = title
    if note is not None:
        locked_cohort.note = note
    locked_cohort.full_clean()
    locked_cohort.save()
    locked_cohort.rooms.set(target_resources)

    if force_release:
        action = "cohort_force_released"
    elif allocation_status == CourseLodgingCohort.AllocationStatus.ALLOCATED:
        action = "cohort_allocated" if creating or before["allocation_status"] != allocation_status else "cohort_updated"
    else:
        action = "cohort_updated"
    after = {
        "allocation_status": allocation_status,
        "is_active": is_active,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "rooms": sorted(target_room_pks),
    }
    if force_release:
        after["release_reason"] = release_reason.strip()
    audit(actor, "bookings.courselodgingcohort", locked_cohort.pk, action, before=before, after=after)
    return locked_cohort


@transaction.atomic
def check_in_student(student: CourseStudentLodging, actor) -> CourseStudentLodging:
    """ยืนยันรายงานตัวนักเรียนที่หน้าที่พัก (สแกน QR บนบัตร).

    ล็อกแถวด้วย select_for_update() ภายใน transaction.atomic() เพื่อกันการยืนยันซ้ำ
    แบบพร้อมกัน (concurrent) — ตรวจสิทธิ์ผู้ยืนยันซ้ำในนี้ด้วย (แม้ view จะกรองสิทธิ์
    ก่อนแล้วก็ตาม) ตามกติกา CLAUDE.md ข้อ 3 ที่กฎธุรกิจต้องอยู่ใน services.py เท่านั้น
    """
    locked_student = (
        CourseStudentLodging.objects.select_related("cohort", "room")
        .select_for_update()
        .get(pk=student.pk)
    )
    if not can_manage_cohort(actor, locked_student.cohort):
        raise PermissionDenied("คุณไม่มีสิทธิ์ยืนยันรายงานตัวของรุ่นนี้")
    if locked_student.checked_in_at is not None:
        raise ValidationError("นักเรียนคนนี้รายงานตัวไปแล้ว ไม่สามารถยืนยันซ้ำได้")

    before = {"checked_in_at": None, "checked_in_by": None}
    locked_student.checked_in_at = timezone.now()
    locked_student.checked_in_by = actor
    locked_student.save(update_fields=["checked_in_at", "checked_in_by"])
    after = {
        "checked_in_at": locked_student.checked_in_at,
        "checked_in_by": locked_student.checked_in_by_id,
    }
    audit(
        actor,
        "bookings.coursestudentlodging",
        locked_student.pk,
        "student_checked_in",
        before=before,
        after=after,
    )
    return locked_student

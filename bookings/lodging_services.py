"""กฎธุรกิจส่วนกลางของการจัดสรรที่พักหลักสูตร.

การแก้ไขห้อง วันที่ สถานะ และจำนวนเตียงต้องผ่าน service นี้ เพื่อให้ทุกช่องทาง
(หน้าจัดการ, Django admin และคำสั่ง seed) ใช้ transaction และกติกาชุดเดียวกัน.
"""

from datetime import date, datetime, time, timedelta
import hashlib
import hmac
from typing import Sequence
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.backends.postgresql.psycopg_any import DateTimeTZRange
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.services import audit
from resources.models import Resource

from .lodging_models import (
    CourseLodgingAccess,
    CourseLodgingCohort,
    CourseLodgingRelease,
    CourseStudentLodging,
    PublicLodgingAccess,
    PublicLodgingThrottle,
)
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
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(
        getattr(user, "is_superuser", False)
        or user.has_perm("bookings.add_courselodgingcohort")
    )


def can_manage_cohort(user, cohort: CourseLodgingCohort) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(
        getattr(user, "is_superuser", False)
        or user.has_perm("bookings.change_courselodgingcohort")
        or cohort.supervisor_id == getattr(user, "pk", None)
    )


def can_access_lodging_management(user) -> bool:
    """Allow course operators and lodging approvers into the shared operations workspace."""
    if not getattr(user, "is_authenticated", False):
        return False
    if (
        getattr(user, "is_superuser", False)
        or user.has_perm("bookings.add_courselodgingcohort")
        or user.has_perm("bookings.change_courselodgingcohort")
    ):
        return True
    if CourseLodgingCohort.objects.filter(supervisor_id=getattr(user, "pk", None)).exists():
        return True

    from approvals.models import ApproverDelegation
    from resources.models import ResourceApprover

    if ResourceApprover.objects.filter(
        user=user,
        resource__resource_type=Resource.Type.ROOM,
        resource__room_category=Resource.Category.LODGING,
    ).exists():
        return True
    delegator_ids = ApproverDelegation.objects.filter(
        delegate=user,
        start_date__lte=timezone.localdate(),
        end_date__gte=timezone.localdate(),
    ).values_list("delegator_id", flat=True)
    return ResourceApprover.objects.filter(
        user_id__in=delegator_ids,
        is_primary=True,
        resource__resource_type=Resource.Type.ROOM,
        resource__room_category=Resource.Category.LODGING,
    ).exists()


def cohort_self_booking_status(cohort: CourseLodgingCohort, now: datetime | None = None) -> tuple[str, str]:
    """Return policy status for student self-booking. Legacy rows without a window stay compatible."""
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    if cohort.allocation_status != CourseLodgingCohort.AllocationStatus.ALLOCATED:
        return "unavailable", "หลักสูตรนี้ยังไม่ได้จัดสรรห้องพัก"
    if cohort.check_out_date < today:
        return "ended", "รอบเข้าพักนี้สิ้นสุดแล้ว"
    if not cohort.is_active:
        return "closed", "หลักสูตรนี้ปิดรับจองอยู่"
    # Backward compatibility: cohorts created before booking-window support remain open
    # while active. All new staff flows write both timestamps.
    if cohort.booking_open_at and now < cohort.booking_open_at:
        return "not_open", "ยังไม่ถึงเวลาเปิดรับจอง"
    if cohort.booking_close_at and now > cohort.booking_close_at:
        return "closed", "หมดเวลารับจองแล้ว"
    return "open", "เปิดรับจอง"


def _public_throttle_digest(scope: str, value: str) -> str:
    payload = f"{scope}:{value}".encode("utf-8")
    return hmac.new(settings.SECRET_KEY.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _public_throttle_window_start(now: datetime) -> datetime:
    window_seconds = max(60, int(getattr(settings, "PUBLIC_LODGING_RATE_WINDOW_SECONDS", 900)))
    epoch = int(now.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % window_seconds), tz=now.tzinfo)


@transaction.atomic
def _consume_public_lodging_quota(*, scope: str, value: str, limit: int, now: datetime | None = None):
    """Consume one anonymous-request quota without storing the raw identifier."""
    now = now or timezone.now()
    limit = max(1, int(limit))
    window_start = _public_throttle_window_start(now)
    key_hash = _public_throttle_digest(scope, value)
    row = (
        PublicLodgingThrottle.objects.select_for_update()
        .filter(scope=scope, key_hash=key_hash, window_start=window_start)
        .first()
    )
    if row is None:
        try:
            with transaction.atomic():
                row = PublicLodgingThrottle.objects.create(
                    scope=scope, key_hash=key_hash, window_start=window_start, count=0
                )
        except IntegrityError:
            row = PublicLodgingThrottle.objects.select_for_update().get(
                scope=scope, key_hash=key_hash, window_start=window_start
            )
    if row.count >= limit:
        raise ValidationError("ส่งคำขอถี่เกินไป กรุณารอสักครู่แล้วลองใหม่")
    row.count += 1
    row.save(update_fields=["count"])
    return row


def _public_lodging_principal():
    """Locked-down service principal used only to anchor anonymous lodging Bookings."""
    from accounts.models import Unit

    unit, _ = Unit.objects.get_or_create(
        code="PUBLIC-LODGE",
        defaults={"name": "บุคคลทั่วไป (คำขอที่พัก)"},
    )
    User = get_user_model()
    domain = getattr(settings, "ALLOWED_EMAIL_DOMAIN", "signalschool.ac.th")
    user, created = User.objects.get_or_create(
        username="public-lodging",
        defaults={
            "email": f"public-lodging@{domain}",
            "first_name": "บุคคลทั่วไป",
            "unit": unit,
            "phone": "SYSTEM",
            "is_active": False,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    elif user.unit_id != unit.pk:
        # Do not silently repurpose an existing named account.
        raise ValidationError("บัญชีระบบสำหรับคำขอที่พักบุคคลทั่วไปมีการตั้งค่าไม่ถูกต้อง")
    if not user.phone:
        user.phone = "SYSTEM"
        user.save(update_fields=["phone"])
    return user


@transaction.atomic
def assign_lodging_bed(*, cohort, room_id, bed_number, rank, full_name,
                       origin_unit, phone, note="", actor=None):
    """Shared public/staff assignment; revalidate state after acquiring locks."""
    cohort = CourseLodgingCohort.objects.select_for_update().get(pk=cohort.pk)
    if actor is not None and not can_manage_cohort(actor, cohort):
        raise PermissionDenied("คุณไม่มีสิทธิ์จัดผู้พักในหลักสูตรนี้")
    if cohort.allocation_status != CourseLodgingCohort.AllocationStatus.ALLOCATED:
        raise ValidationError("ต้องจัดสรรห้องให้หลักสูตรก่อนจัดผู้พัก")
    if actor is None:
        booking_state, booking_message = cohort_self_booking_status(cohort)
        if booking_state != "open":
            raise ValidationError(booking_message)
    elif cohort.check_out_date < timezone.localdate():
        raise ValidationError("รอบเข้าพักนี้สิ้นสุดแล้ว")
    try:
        bed_number = int(bed_number)
        room = Resource.objects.select_for_update().get(pk=room_id)
    except (TypeError, ValueError, Resource.DoesNotExist):
        raise ValidationError("กรุณาเลือกห้องและเตียงให้ถูกต้อง")
    if not cohort.rooms.filter(pk=room.pk).exists() or room.status != Resource.Status.ACTIVE:
        raise ValidationError("ห้องนี้ไม่พร้อมให้จัดผู้พักในหลักสูตรนี้")
    if not 1 <= bed_number <= cohort.beds_per_room:
        raise ValidationError("หมายเลขเตียงไม่ถูกต้อง")
    phone = normalize_phone(phone)
    values = {key: (value or "").strip() for key, value in
              dict(rank=rank, full_name=full_name, origin_unit=origin_unit, phone=phone).items()}
    if not all(values.values()):
        raise ValidationError("กรุณากรอกยศ ชื่อ-สกุล สังกัด และเบอร์โทรให้ครบ")
    if cohort.students.filter(room=room, bed_number=bed_number).exists():
        raise ValidationError("เตียงนี้มีเพื่อนร่วมรุ่นเพิ่งจองไปแล้ว กรุณาเลือกเตียงอื่น")
    if cohort.students.filter(phone=phone).exists():
        raise ValidationError("เบอร์โทรศัพท์นี้ลงทะเบียนในรอบนี้แล้ว")
    student = CourseStudentLodging.objects.create(
        cohort=cohort, room=room, bed_number=bed_number, note=note, **values)
    if actor is None:
        CourseLodgingAccess.objects.create(student=student)
    audit(actor, "bookings.coursestudentlodging", student.pk,
          "lodging_bed_assigned", after={"cohort": str(cohort.pk), "room": room.code,
                                        "bed_number": bed_number, "by_staff": actor is not None})
    return student


@transaction.atomic
def move_lodging_bed(*, student: CourseStudentLodging, room_id, bed_number, actor) -> CourseStudentLodging:
    """Move a course guest to another allocated bed with row/resource locking and audit."""
    locked_student = (
        CourseStudentLodging.objects.select_related("cohort", "room")
        .select_for_update()
        .get(pk=student.pk)
    )
    cohort = CourseLodgingCohort.objects.select_for_update().get(pk=locked_student.cohort_id)
    if not can_manage_cohort(actor, cohort):
        raise PermissionDenied("คุณไม่มีสิทธิ์ย้ายผู้เข้าพักของหลักสูตรนี้")
    if cohort.allocation_status != CourseLodgingCohort.AllocationStatus.ALLOCATED:
        raise ValidationError("หลักสูตรนี้ยังไม่ได้จัดสรรห้องพัก")
    if cohort.check_out_date < timezone.localdate():
        raise ValidationError("รอบเข้าพักนี้สิ้นสุดแล้ว")
    try:
        bed_number = int(bed_number)
        room = Resource.objects.select_for_update().get(pk=room_id)
    except (TypeError, ValueError, Resource.DoesNotExist):
        raise ValidationError("กรุณาเลือกห้องและเตียงปลายทางให้ถูกต้อง")
    if not cohort.rooms.filter(pk=room.pk).exists() or room.status != Resource.Status.ACTIVE:
        raise ValidationError("ห้องปลายทางไม่ได้อยู่ในรายการห้องพักที่พร้อมใช้งานของหลักสูตรนี้")
    if not 1 <= bed_number <= cohort.beds_per_room:
        raise ValidationError("หมายเลขเตียงปลายทางไม่ถูกต้อง")
    if locked_student.room_id == room.pk and locked_student.bed_number == bed_number:
        raise ValidationError("ผู้เข้าพักอยู่ที่เตียงนี้อยู่แล้ว")
    if CourseStudentLodging.objects.filter(
        cohort=cohort, room=room, bed_number=bed_number
    ).exclude(pk=locked_student.pk).exists():
        raise ValidationError("เตียงปลายทางมีผู้เข้าพักแล้ว กรุณาเลือกเตียงอื่น")

    before = {"room": locked_student.room.code, "bed_number": locked_student.bed_number}
    locked_student.room = room
    locked_student.bed_number = bed_number
    locked_student.save(update_fields=["room", "bed_number"])
    audit(
        actor,
        "bookings.coursestudentlodging",
        locked_student.pk,
        "lodging_bed_moved",
        before=before,
        after={"room": room.code, "bed_number": bed_number},
    )
    return locked_student


@transaction.atomic
def release_lodging_reservation(
    *,
    student: CourseStudentLodging,
    outcome: str,
    actor=None,
    access_token=None,
    reason: str = "",
    now: datetime | None = None,
) -> CourseLodgingRelease:
    """Remove an active bed reservation while preserving immutable operational history."""
    now = now or timezone.now()
    current = CourseStudentLodging.objects.only("cohort_id", "room_id").get(pk=student.pk)
    cohort = CourseLodgingCohort.objects.select_for_update().get(pk=current.cohort_id)
    room = Resource.objects.select_for_update().get(pk=current.room_id)
    locked = (
        CourseStudentLodging.objects.select_related("cohort", "room")
        .select_for_update()
        .get(pk=student.pk)
    )
    if locked.checked_in_at is not None:
        raise ValidationError("ผู้เข้าพักรายงานตัวแล้ว ไม่สามารถปล่อยเตียงด้วยขั้นตอนนี้")
    if outcome not in CourseLodgingRelease.Outcome.values:
        raise ValidationError("ผลการปล่อยเตียงไม่ถูกต้อง")

    today = timezone.localtime(now).date()
    authenticated = bool(getattr(actor, "is_authenticated", False))
    if authenticated:
        if not can_manage_cohort(actor, cohort):
            raise PermissionDenied("คุณไม่มีสิทธิ์ยกเลิกหรือบันทึกไม่มารายงานตัวของหลักสูตรนี้")
        channel = CourseLodgingRelease.Channel.STAFF
        if today > cohort.check_out_date:
            raise ValidationError("รอบเข้าพักนี้สิ้นสุดแล้ว")
        if outcome == CourseLodgingRelease.Outcome.NO_SHOW and today < cohort.check_in_date:
            raise ValidationError("ยังไม่ถึงวันเข้าพัก จึงยังบันทึกเป็นไม่มารายงานตัวไม่ได้")
    else:
        if outcome != CourseLodgingRelease.Outcome.CANCELLED:
            raise PermissionDenied("การบันทึกไม่มารายงานตัวทำได้โดยเจ้าหน้าที่เท่านั้น")
        if not access_token:
            raise PermissionDenied("ลิงก์จัดการการจองไม่ถูกต้อง")
        access = (
            CourseLodgingAccess.objects.select_for_update()
            .filter(pk=access_token, student=locked)
            .first()
        )
        if access is None:
            raise PermissionDenied("ลิงก์จัดการการจองไม่ถูกต้อง")
        booking_state, booking_message = cohort_self_booking_status(cohort, now=now)
        if booking_state != "open":
            raise ValidationError(f"ยกเลิกด้วยตนเองไม่ได้: {booking_message}")
        channel = CourseLodgingRelease.Channel.SELF_SERVICE

    snapshot = {
        "cohort": str(cohort.pk),
        "room": room.code,
        "bed_number": locked.bed_number,
        "rank": locked.rank,
        "full_name": locked.full_name,
        "origin_unit": locked.origin_unit,
        "phone": locked.phone,
        "note": locked.note,
        "booked_at": locked.booked_at,
    }
    release = CourseLodgingRelease.objects.create(
        original_student_id=locked.pk,
        cohort=cohort,
        room=room,
        bed_number=locked.bed_number,
        rank=locked.rank,
        full_name=locked.full_name,
        origin_unit=locked.origin_unit,
        phone=locked.phone,
        note=locked.note,
        booked_at=locked.booked_at,
        outcome=outcome,
        channel=channel,
        reason=(reason or "").strip(),
        released_by=actor if authenticated else None,
    )
    action = (
        "lodging_no_show"
        if outcome == CourseLodgingRelease.Outcome.NO_SHOW
        else "lodging_reservation_cancelled"
    )
    audit(
        actor,
        "bookings.coursestudentlodging",
        locked.pk,
        action,
        before=snapshot,
        after={
            "release_id": str(release.pk),
            "outcome": outcome,
            "channel": channel,
            "reason": release.reason,
        },
    )
    locked.delete()
    return release


@transaction.atomic
def set_cohort_self_booking(*, cohort: CourseLodgingCohort, actor, enabled: bool) -> CourseLodgingCohort:
    """Quick open/close action for staff; preserves allocation and uses the shared allocation service."""
    locked = CourseLodgingCohort.objects.select_for_update().get(pk=cohort.pk)
    if not can_manage_cohort(actor, locked):
        raise PermissionDenied("คุณไม่มีสิทธิ์เปิดหรือปิดรับจองของหลักสูตรนี้")
    if locked.allocation_status != CourseLodgingCohort.AllocationStatus.ALLOCATED:
        raise ValidationError("ต้องจัดสรรห้องให้หลักสูตรก่อนเปิดรับจอง")
    today = timezone.localdate()
    if locked.check_out_date < today:
        raise ValidationError("รอบเข้าพักนี้สิ้นสุดแล้ว")

    booking_open_at = locked.booking_open_at
    booking_close_at = locked.booking_close_at
    if enabled:
        now = timezone.now()
        if locked.check_in_date < today:
            raise ValidationError("ไม่สามารถเปิดรับจองใหม่หลังวันเริ่มเข้าพักแล้ว")
        if booking_open_at is None or booking_open_at > now:
            booking_open_at = now
        if booking_close_at is None or booking_close_at <= now:
            booking_close_at = timezone.make_aware(
                datetime.combine(locked.check_in_date, time(23, 59)),
                timezone.get_current_timezone(),
            )
        if booking_close_at <= now:
            raise ValidationError("ช่วงเวลารับจองสิ้นสุดแล้ว กรุณาปรับช่วงเวลาใหม่")

    return update_cohort_allocation(
        cohort=locked,
        rooms=list(locked.rooms.all()),
        check_in_date=locked.check_in_date,
        check_out_date=locked.check_out_date,
        allocation_status=locked.allocation_status,
        is_active=enabled,
        beds_per_room=locked.beds_per_room,
        booking_open_at=booking_open_at,
        booking_close_at=booking_close_at,
        actor=actor,
    )


def request_general_lodging(
    *, actor=None, room, check_in, check_out, phone, note="", guest_name="", client_key=""
):
    """Create an idempotent general/public lodging request on Booking Core."""
    from .models import Booking
    from .services import submit_booking

    authenticated = bool(getattr(actor, "is_authenticated", False))
    if authenticated:
        if not actor.unit_id:
            raise ValidationError("บัญชีผู้ใช้ต้องระบุหน่วยงานก่อนส่งคำขอ")
        requester = actor
        responsible_name = actor.display_name
    else:
        responsible_name = (guest_name or "").strip()
        if not responsible_name:
            raise ValidationError("กรุณาระบุชื่อผู้เข้าพัก")
        requester = _public_lodging_principal()
    phone = normalize_phone(phone)
    if not phone:
        raise ValidationError("กรุณาระบุเบอร์โทรศัพท์ที่ถูกต้อง")
    if room.room_category != Resource.Category.LODGING:
        raise ValidationError("เลือกได้เฉพาะห้องพัก")
    if check_out <= check_in:
        raise ValidationError("วันออกต้องอยู่หลังวันเข้า")
    zone = timezone.get_current_timezone()
    start_at = timezone.make_aware(datetime.combine(check_in, time(14)), zone)
    end_at = timezone.make_aware(datetime.combine(check_out, time(12)), zone)

    existing = (
        Booking.objects.filter(
            room=room,
            title="คำขอเข้าพักทั่วไป",
            responsible_phone=phone,
            start_at=start_at,
            end_at=end_at,
            request_status__in=[Booking.RequestStatus.PENDING, Booking.RequestStatus.APPROVED],
            public_lodging_access__isnull=False,
        )
        .order_by("created_at")
        .first()
    )
    if existing is not None:
        raise ValidationError("มีคำขอเข้าพักช่วงนี้ด้วยเบอร์โทรนี้อยู่แล้ว กรุณาใช้ลิงก์ติดตามคำขอเดิม")

    if not authenticated:
        _consume_public_lodging_quota(
            scope=PublicLodgingThrottle.Scope.PHONE,
            value=phone,
            limit=getattr(settings, "PUBLIC_LODGING_RATE_PHONE_LIMIT", 3),
        )
        if client_key:
            _consume_public_lodging_quota(
                scope=PublicLodgingThrottle.Scope.CLIENT,
                value=str(client_key),
                limit=getattr(settings, "PUBLIC_LODGING_RATE_CLIENT_LIMIT", 8),
            )

    with transaction.atomic():
        booking = Booking(
            room=room, requester=requester, unit=requester.unit,
            title="คำขอเข้าพักทั่วไป", purpose=Booking.Purpose.OTHER,
            responsible_name=responsible_name, responsible_phone=phone,
            start_at=start_at, end_at=end_at,
            visibility=Booking.Visibility.RESTRICTED, note=note,
        )
        booking.full_clean()
        booking.save()
        booking = submit_booking(booking)
        PublicLodgingAccess.objects.create(booking=booking)
        return booking


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
    booking_open_at: datetime | None = None,
    booking_close_at: datetime | None = None,
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
        if booking_open_at is None and booking_close_at is None:
            booking_open_at = locked_cohort.booking_open_at
            booking_close_at = locked_cohort.booking_close_at

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
    if booking_open_at and booking_close_at and booking_close_at < booking_open_at:
        raise ValidationError({"booking_close_at": "เวลาปิดรับจองต้องไม่ก่อนเวลาเปิดรับจอง"})
    if is_active and (booking_open_at is None) != (booking_close_at is None):
        raise ValidationError("กรุณากำหนดทั้งเวลาเปิดและปิดรับจอง")
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
        "booking_open_at": getattr(locked_cohort, "booking_open_at", None),
        "booking_close_at": getattr(locked_cohort, "booking_close_at", None),
        "rooms": sorted(current_room_pks),
    }
    locked_cohort.check_in_date = check_in_date
    locked_cohort.check_out_date = check_out_date
    locked_cohort.allocation_status = allocation_status
    locked_cohort.is_active = is_active
    locked_cohort.booking_open_at = booking_open_at
    locked_cohort.booking_close_at = booking_close_at
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
        "booking_open_at": booking_open_at,
        "booking_close_at": booking_close_at,
        "rooms": sorted(target_room_pks),
    }
    if force_release:
        after["release_reason"] = release_reason.strip()
    audit(actor, "bookings.courselodgingcohort", locked_cohort.pk, action, before=before, after=after)
    return locked_cohort


@transaction.atomic
def check_in_student(student: CourseStudentLodging, actor, now: datetime | None = None) -> CourseStudentLodging:
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
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    if today < locked_student.cohort.check_in_date:
        raise ValidationError("ยังไม่ถึงวันเข้าพัก จึงยังยืนยันรายงานตัวไม่ได้")
    if today > locked_student.cohort.check_out_date:
        raise ValidationError("รอบเข้าพักสิ้นสุดแล้ว ไม่สามารถยืนยันรายงานตัวได้")

    before = {"checked_in_at": None, "checked_in_by": None}
    locked_student.checked_in_at = now
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

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import audit, model_snapshot
from notifications.services import notify_submitted
from resources.models import Resource, ResourceRule

from .course_catalog import selectable_course_runs
from .models import Booking, CourseRun
from .services import BookingConflict, find_available_rooms, submit_booking


@transaction.atomic
def create_online_teaching_booking(*, user, room, start_at, end_at, course_run, purpose) -> Booking:
    """สร้างการจองห้องสอนออนไลน์ผ่านกฎเดียวกันสำหรับหน้าใหม่และลิงก์เดิม."""
    from .online_teaching import ONLINE_TEACHING_ROOM_CODES, can_book_online_teaching

    if not can_book_online_teaching(user):
        raise PermissionDenied("เฉพาะครูที่ได้รับสิทธิ์จองห้องสอนออนไลน์")
    if room.resource_type != Resource.Type.ROOM or room.room_category != Resource.Category.ONLINE:
        raise ValidationError("ห้องที่เลือกไม่ใช่ห้องสอนออนไลน์")
    if room.code not in ONLINE_TEACHING_ROOM_CODES or room.status != Resource.Status.ACTIVE:
        raise ValidationError("ห้องนี้ไม่อยู่ในรายการห้องสอนออนไลน์ที่เปิดใช้")
    rule = getattr(room, "rule", None)
    if rule is None or rule.approval_policy != ResourceRule.ApprovalPolicy.AUTO:
        raise PermissionDenied("ห้องนี้ยังไม่ได้ตั้งนโยบายจองอัตโนมัติสำหรับครู")
    if not user.unit_id:
        raise ValidationError("บัญชีครูต้องมีสังกัดก่อนจองห้อง")
    if not (user.phone or "").strip():
        raise ValidationError("บัญชีครูต้องมีเบอร์โทรศัพท์ก่อนจองห้อง")
    if not isinstance(course_run, CourseRun) or not selectable_course_runs().filter(pk=course_run.pk).exists():
        raise ValidationError("หลักสูตร/รุ่นนี้ไม่ได้อยู่ในรายการที่เปิดใช้")

    course_title = course_run.display_name
    booking = Booking(
        room=room,
        requester=user,
        unit=user.unit,
        responsible_name=user.display_name,
        responsible_phone=(user.phone or "").strip(),
        course_run=course_run,
        title=course_title,
        attendee_level=course_title,
        purpose=purpose,
        start_at=start_at,
        end_at=end_at,
        attendees=1,
        visibility=Booking.Visibility.NORMAL,
        has_external_attendees=False,
    )
    booking.full_clean()
    booking.save()
    submit_booking(booking)
    if booking.request_status != Booking.RequestStatus.APPROVED:
        raise ValidationError("นโยบายห้องไม่อนุญาตการยืนยันอัตโนมัติ")

    audit(
        user,
        "bookings.booking",
        booking.pk,
        "online_teaching_booked",
        after=model_snapshot(booking),
    )
    notify_submitted(booking)
    return booking


def _bookable_online_rooms(user, start_at, end_at) -> list[Resource]:
    from .online_teaching import ONLINE_TEACHING_ROOM_CODES

    available, _ = find_available_rooms(
        start_at,
        end_at,
        user,
        room_categories=(Resource.Category.ONLINE,),
    )
    rooms = []
    for item in available:
        room = item.room
        rule = getattr(room, "rule", None)
        if (
            room.code in ONLINE_TEACHING_ROOM_CODES
            and rule is not None
            and rule.approval_policy == ResourceRule.ApprovalPolicy.AUTO
        ):
            rooms.append(room)
    return sorted(rooms, key=lambda room: room.code)


def suggest_online_rooms(*, user, start_at, end_at) -> tuple[list[Resource], list[dict]]:
    """คืนห้องว่างและช่วงใกล้เคียงสูงสุด 3 ช่วง (ทีละ 30 นาที ภายในวันเดียวกัน)."""
    rooms = _bookable_online_rooms(user, start_at, end_at)
    duration = end_at - start_at
    if rooms or duration <= timedelta(0):
        return rooms, []

    local_start = timezone.localtime(start_at)
    target_day = local_start.date()
    now = timezone.now()
    alternatives = []
    seen = set()
    for distance in range(1, 7):  # 30 นาที ... 3 ชั่วโมง
        for sign in (1, -1):
            candidate_start = start_at + timedelta(minutes=30 * distance * sign)
            candidate_end = candidate_start + duration
            if timezone.localtime(candidate_start).date() != target_day:
                continue
            if timezone.localtime(candidate_end).date() != target_day:
                continue
            if candidate_start < now:
                continue
            key = (candidate_start, candidate_end)
            if key in seen:
                continue
            seen.add(key)
            candidate_rooms = _bookable_online_rooms(user, candidate_start, candidate_end)
            if candidate_rooms:
                alternatives.append(
                    {
                        "start_at": candidate_start,
                        "end_at": candidate_end,
                        "rooms": candidate_rooms,
                        "available_count": len(candidate_rooms),
                    }
                )
                if len(alternatives) == 3:
                    return rooms, alternatives
    return rooms, alternatives

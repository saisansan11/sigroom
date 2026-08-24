from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from audit.services import audit
from bookings.models import Booking
from notifications.services import booking_ref, notify
from resources.models import Resource


def can_manage_usage(user, room=None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    rooms = user.custodied_resources.filter(resource_type=Resource.Type.ROOM)
    return rooms.filter(pk=room.pk).exists() if room is not None else rooms.exists()


def managed_room_ids(user):
    if user.is_superuser:
        return None
    return user.custodied_resources.filter(resource_type=Resource.Type.ROOM).values_list("pk", flat=True)


def recent_bookings_for(user, now=None):
    if not can_manage_usage(user):
        raise PermissionError("เฉพาะเจ้าหน้าที่ดูแลห้องหรือผู้ดูแลระบบเท่านั้น")
    now = now or timezone.now()
    today = timezone.localdate(now)
    start_date = today - timedelta(days=3)
    queryset = Booking.objects.filter(
        request_status=Booking.RequestStatus.APPROVED,
        end_at__date__gte=start_date,
        end_at__date__lte=today,
    ).select_related("room", "requester", "unit").order_by("-end_at", "room__code")
    room_ids = managed_room_ids(user)
    if room_ids is not None:
        queryset = queryset.filter(room_id__in=room_ids)
    return queryset


def usage_change_is_open(booking, now=None) -> bool:
    now = now or timezone.now()
    if booking.request_status != Booking.RequestStatus.APPROVED or booking.usage_status not in {
        Booking.UsageStatus.UPCOMING,
        Booking.UsageStatus.USED,
        Booking.UsageStatus.NO_SHOW,
    }:
        return False
    if now < booking.end_at:
        return False
    use_date = timezone.localtime(booking.end_at).date()
    return timezone.localdate(now) <= use_date + timedelta(days=3)


@transaction.atomic
def set_usage_status(booking, user, status, now=None):
    now = now or timezone.now()
    locked = Booking.objects.select_for_update().select_related("room", "requester").get(pk=booking.pk)
    if not can_manage_usage(user, locked.room):
        raise PermissionError("คุณไม่มีสิทธิ์เปลี่ยนสถานะการใช้ห้องนี้")
    if locked.request_status != Booking.RequestStatus.APPROVED:
        raise ValidationError("เปลี่ยนสถานะการใช้งานได้เฉพาะการจองที่อนุมัติแล้ว")
    if status not in {Booking.UsageStatus.USED, Booking.UsageStatus.NO_SHOW}:
        raise ValidationError("สถานะการใช้งานไม่ถูกต้อง")
    if locked.usage_status in {Booking.UsageStatus.DISPLACED, Booking.UsageStatus.ROOM_UNAVAILABLE}:
        raise ValidationError("การจองที่ถูกย้ายหรือห้องใช้งานไม่ได้ไม่สามารถเปลี่ยนเป็นใช้งานแล้ว/ไม่มาใช้")
    if not usage_change_is_open(locked, now):
        raise ValidationError("แก้สถานะได้หลังสิ้นสุดการใช้ห้องและไม่เกิน 3 วันเท่านั้น")
    before = locked.usage_status
    if before == status:
        return locked
    locked.usage_status = status
    locked.save(update_fields=["usage_status", "updated_at"])
    audit(user, "bookings.booking", locked.pk, "usage_status_changed", before={"usage_status": before}, after={"usage_status": status})
    if status == Booking.UsageStatus.NO_SHOW:
        notify(
            [locked.requester],
            f"การจอง [BK-{booking_ref(locked)}] ถูกบันทึกว่าไม่มาใช้",
            f"/bookings/{locked.pk}/",
            locked,
        )
    return locked


def mark_finished_bookings_used(now=None) -> int:
    """ปิด UPCOMING ที่จบแล้วเป็น USED ทีละรายการเพื่อบันทึก audit และรันซ้ำได้"""
    now = now or timezone.now()
    booking_ids = list(
        Booking.objects.filter(
            request_status=Booking.RequestStatus.APPROVED,
            usage_status=Booking.UsageStatus.UPCOMING,
            end_at__lt=now,
        ).values_list("pk", flat=True)
    )
    changed = 0
    for booking_id in booking_ids:
        with transaction.atomic():
            booking = Booking.objects.select_for_update().get(pk=booking_id)
            if (
                booking.request_status != Booking.RequestStatus.APPROVED
                or booking.usage_status != Booking.UsageStatus.UPCOMING
                or booking.end_at >= now
            ):
                continue
            booking.usage_status = Booking.UsageStatus.USED
            booking.save(update_fields=["usage_status", "updated_at"])
            audit(None, "bookings.booking", booking.pk, "usage_status_auto_used", before={"usage_status": Booking.UsageStatus.UPCOMING}, after={"usage_status": Booking.UsageStatus.USED})
            changed += 1
    return changed

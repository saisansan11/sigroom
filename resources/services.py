from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Blackout, Resource, ResourceOutage


def active_blackouts(resource: Resource, start: datetime, end: datetime) -> list[Blackout]:
    candidates = Blackout.objects.filter(start_at__lt=end, end_at__gt=start).prefetch_related("rooms")
    return [item for item in candidates if item.applies_to(resource)]


def active_outages(resource: Resource, start: datetime, end: datetime) -> list[ResourceOutage]:
    return list(
        ResourceOutage.objects.filter(
            resource=resource,
            ended_early_at__isnull=True,
            start_at__lt=end,
            end_at__gt=start,
        ).select_related("resource", "created_by")
    )


def can_manage_outage(user, resource: Resource) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (user.is_superuser or resource.custodians.filter(pk=user.pk).exists())
    )


def affected_bookings(resource: Resource, start: datetime, end: datetime):
    from bookings.models import Booking

    return (
        Booking.objects.filter(
            room=resource,
            request_status__in=Booking.HOLDING_STATUSES,
            start_at__lt=end,
            end_at__gt=start,
        )
        .select_related("requester", "room", "unit")
        .order_by("start_at")
    )


@transaction.atomic
def create_outage(
    resource: Resource,
    user,
    start: datetime,
    end: datetime,
    reason: str,
) -> tuple[ResourceOutage, list]:
    from bookings.models import Booking
    from notifications.services import booking_summary, notify

    if not can_manage_outage(user, resource):
        raise PermissionError("เฉพาะเจ้าหน้าที่ดูแลห้องหรือผู้ดูแลระบบเท่านั้นที่ตั้งงดใช้ได้")
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("กรุณาระบุเหตุผลงดใช้ห้อง")
    if end <= start:
        raise ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม")

    outage = ResourceOutage.objects.create(
        resource=resource,
        start_at=start,
        end_at=end,
        reason=reason,
        created_by=user,
    )
    affected = list(affected_bookings(resource, start, end))
    for booking in affected:
        booking.usage_status = Booking.UsageStatus.ROOM_UNAVAILABLE
        booking.save(update_fields=["usage_status", "updated_at"])
        notify(
            [booking.requester],
            f"คำขอ {booking_summary(booking)} ได้รับผลกระทบจากห้องงดใช้: {reason}",
            f"/bookings/{booking.pk}/",
            booking,
        )
    notify(
        resource.custodians.all(),
        f"ตั้งงดใช้ {resource.code}: {reason} · กระทบ {len(affected)} รายการ",
        f"/resources/{resource.code}/outage/",
    )
    return outage, affected


@transaction.atomic
def end_outage_early(outage: ResourceOutage, user, now: datetime | None = None) -> list:
    from bookings.models import Booking
    from notifications.services import booking_summary, notify

    if not can_manage_outage(user, outage.resource):
        raise PermissionError("คุณไม่มีสิทธิ์สิ้นสุดช่วงงดใช้นี้")
    if outage.ended_early_at is not None:
        raise ValueError("ช่วงงดใช้นี้สิ้นสุดก่อนกำหนดแล้ว")
    now = now or timezone.now()
    outage.ended_early_at = now
    outage.save(update_fields=["ended_early_at"])

    restored = []
    candidates = Booking.objects.filter(
        room=outage.resource,
        usage_status=Booking.UsageStatus.ROOM_UNAVAILABLE,
        start_at__lt=outage.end_at,
        end_at__gt=outage.start_at,
    ).select_related("requester", "room")
    for booking in candidates:
        if active_outages(outage.resource, booking.start_at, booking.end_at):
            continue
        booking.usage_status = Booking.UsageStatus.UPCOMING
        booking.save(update_fields=["usage_status", "updated_at"])
        restored.append(booking)
        notify(
            [booking.requester],
            f"ห้องกลับมาใช้งานได้สำหรับคำขอ {booking_summary(booking)}",
            f"/bookings/{booking.pk}/",
            booking,
        )
    notify(
        outage.resource.custodians.all(),
        f"สิ้นสุดงดใช้ {outage.resource.code} ก่อนกำหนด · คืนสถานะ {len(restored)} รายการ",
        f"/resources/{outage.resource.code}/outage/",
    )
    return restored


def recent_outage_reasons(user, limit: int = 10) -> list[str]:
    values = (
        ResourceOutage.objects.filter(created_by=user)
        .exclude(reason="")
        .order_by("-created_at")
        .values_list("reason", flat=True)
    )
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
        if len(result) == limit:
            break
    return result

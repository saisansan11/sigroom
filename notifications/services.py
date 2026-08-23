from collections.abc import Iterable

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Notification


def booking_ref(booking) -> str:
    return str(booking.pk).replace("-", "")[:8].upper()


def booking_summary(booking) -> str:
    local_start = timezone.localtime(booking.start_at)
    buddhist_year = local_start.year + 543
    return (
        f"[{booking_ref(booking)}] {booking.room.code} "
        f"{local_start.day:02d}/{local_start.month:02d}/{buddhist_year} "
        f"{local_start:%H:%M}"
    )


def notify(users: Iterable, text: str, url: str = "", booking=None) -> list[Notification]:
    """สร้างการแจ้งเตือนครั้งละหนึ่งรายการต่อผู้ใช้ โดยตัดผู้รับซ้ำออก"""
    unique_users = {user.pk: user for user in users if user and getattr(user, "pk", None)}
    if booking and booking.title:
        text = text.replace(booking.title, "กิจกรรม")
    return Notification.objects.bulk_create(
        [
            Notification(user=user, text=text[:300], url=url[:200], booking=booking)
            for user in unique_users.values()
        ]
    )


def unread_count(user) -> int:
    if not getattr(user, "is_authenticated", False):
        return 0
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


@transaction.atomic
def mark_read(user, notification_id=None, *, all=False) -> int:
    queryset = Notification.objects.filter(user=user, read_at__isnull=True)
    if not all:
        queryset = queryset.filter(pk=notification_id)
    return queryset.update(read_at=timezone.now())


def notify_submitted(booking) -> None:
    """hook หลัง submit_booking สำเร็จ; ไม่แก้ตรรกะภายใน submit_booking เดิม"""
    from approvals.models import Approval
    from approvals.services import effective_approver_ids
    from accounts.models import User

    detail_url = reverse("bookings:booking_detail", args=[booking.pk])
    summary = booking_summary(booking)
    Approval.objects.get_or_create(booking=booking, action=Approval.Action.SUBMITTED)
    notify(
        [booking.requester],
        f"ส่งคำขอ {summary} แล้ว · สถานะ {booking.get_request_status_display()}",
        detail_url,
        booking,
    )
    if booking.request_status != booking.RequestStatus.PENDING:
        return

    approver_ids = effective_approver_ids(booking.room, timezone.now())
    recipient_ids = set(approver_ids["primary_ids"])
    if booking.is_urgent:
        recipient_ids.update(approver_ids["backup_ids"])
    recipients = User.objects.filter(pk__in=recipient_ids)
    urgent = " (เร่งด่วน)" if booking.is_urgent else ""
    notify(
        recipients,
        f"มีคำขอใหม่รออนุมัติ: {summary}{urgent}",
        detail_url,
        booking,
    )

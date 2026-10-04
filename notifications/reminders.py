"""แจ้งผู้จองก่อนสอน โดยมีฐานข้อมูลเป็นผู้กันแจ้งซ้ำแต่ละรอบ"""

import logging
from datetime import timedelta
from math import ceil

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from resources.models import Resource

from .models import Notification
from .services import booking_summary

logger = logging.getLogger(__name__)
REMINDER_CATEGORIES = (Resource.Category.ONLINE,)


def _reminder_kind(booking, now):
    if booking.start_at <= now < booking.start_at + timedelta(minutes=10):
        return "remind_start"
    submitted_at = booking.submitted_at or booking.created_at
    if (
        submitted_at <= booking.start_at - timedelta(minutes=30)
        and booking.start_at - timedelta(minutes=30) <= now
        < booking.start_at - timedelta(minutes=5)
    ):
        return "remind_30"
    return None


def _deliver_email(booking, kind, text, pass_path, counts):
    """ล้มเหลวเฉพาะอีเมล; แถวกระดิ่งที่ commit แล้วและงานอื่นยังทำงานได้"""
    try:
        if not booking.requester.email:
            raise ValueError("ผู้จองไม่มีอีเมลสำหรับรับการแจ้งเตือน")
        base_url = settings.PUBLIC_BASE_URL.rstrip("/")
        lines = [text, f"ดูบัตรจอง: {base_url}{pass_path}"]
        # ส่งเฉพาะเจ้าของการจอง ไม่คัดลอกผู้อนุมัติหรือผู้ร่วมหน่วยงาน
        if booking.online_meeting_url:
            lines.append(f"เข้าห้องเรียนออนไลน์: {booking.online_meeting_url}")
        delivered = send_mail(
            "SIGROOM · เตือนก่อนสอน" if kind == "remind_30" else "SIGROOM · ถึงเวลาสอนแล้ว",
            "\n\n".join(lines),
            settings.DEFAULT_FROM_EMAIL,
            [booking.requester.email],
            fail_silently=False,
        )
        if not delivered:
            raise RuntimeError("ระบบอีเมลไม่รับข้อความ")
    except Exception as exc:
        counts["email_failed"] += 1
        # ไม่ log exception text/traceback เพราะ backend อาจแทรกรหัสผ่านหรือเนื้อหาอีเมล
        logger.warning(
            "teaching_reminder_email_failed booking=%s kind=%s error_type=%s",
            booking.pk,
            kind,
            type(exc).__name__,
        )


def _deliver_push(booking, kind, text, pass_path):
    """Push เป็นช่องทางแยกจาก email: ช่องทางใดล้มต้องไม่ขวางอีกช่องทางหรืองาน scheduled อื่น"""
    try:
        from .push import send_push

        title = "SIGROOM · เตือนก่อนสอน" if kind == "remind_30" else "SIGROOM · ถึงเวลาสอนแล้ว"
        send_push(booking.requester, title, text, pass_path)
    except Exception as exc:
        # ไม่ log endpoint, key, payload หรือ exception text
        logger.warning(
            "teaching_reminder_push_failed booking=%s kind=%s error_type=%s",
            booking.pk,
            kind,
            type(exc).__name__,
        )


def send_teaching_reminders(now=None) -> dict[str, int]:
    """ผล email_failed นับเมื่อ on_commit ทำงาน; run_jobs เรียกนอก outer atomic"""
    now = now or timezone.now()
    counts = {"remind_30": 0, "remind_start": 0, "email_failed": 0}
    candidates = Booking.objects.filter(
        request_status=Booking.RequestStatus.APPROVED,
        usage_status=Booking.UsageStatus.UPCOMING,
        room__room_category__in=REMINDER_CATEGORIES,
    ).filter(
        Q(start_at__gt=now + timedelta(minutes=5), start_at__lte=now + timedelta(minutes=30))
        | Q(start_at__gt=now - timedelta(minutes=10), start_at__lte=now)
    ).order_by("pk").values_list("pk", flat=True)
    for booking_id in candidates.iterator():
        try:
            with transaction.atomic():
                # อ่านสถานะอีกครั้งใต้ lock เพื่อไม่เตือนคำขอที่เพิ่งถูกยกเลิก/แก้เวลา
                booking = (
                    Booking.objects.select_for_update(of=("self",))
                    .select_related("room", "requester")
                    .get(pk=booking_id)
                )
                if (
                    booking.request_status != Booking.RequestStatus.APPROVED
                    or booking.usage_status != Booking.UsageStatus.UPCOMING
                    or booking.room.room_category not in REMINDER_CATEGORIES
                ):
                    continue
                kind = _reminder_kind(booking, now)
                if not kind:
                    continue
                local_end = timezone.localtime(booking.end_at)
                minutes_left = ceil((booking.start_at - now).total_seconds() / 60)
                lead = f"อีก {minutes_left} นาทีถึงเวลาสอน" if kind == "remind_30" else "ถึงเวลาสอนแล้ว"
                text = f"{lead} · {booking_summary(booking)}–{local_end:%H:%M}"
                pass_path = reverse("bookings:booking_pass", args=[booking.pk])
                _, created = Notification.objects.get_or_create(
                    booking=booking,
                    user=booking.requester,
                    kind=kind,
                    defaults={"text": text[:300], "url": pass_path},
                )
                if created:
                    counts[kind] += 1
                    transaction.on_commit(
                        lambda booking=booking, kind=kind, text=text, path=pass_path:
                        _deliver_email(booking, kind, text, path, counts)
                    )
                    transaction.on_commit(
                        lambda booking=booking, kind=kind, text=text, path=pass_path:
                        _deliver_push(booking, kind, text, path)
                    )
        except IntegrityError as exc:
            # อยู่นอก atomic: การชน constraint ไม่ทำให้ transaction ของงานถัดไปเสีย
            cause = getattr(exc, "__cause__", None)
            constraint = getattr(getattr(cause, "diag", None), "constraint_name", None)
            if constraint != "uniq_notification_booking_user_kind":
                raise
    return counts

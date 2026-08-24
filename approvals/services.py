from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Min
from django.utils import timezone

from bookings.models import Booking
from bookings.services import release_holds
from resources.models import ResourceApprover

from .models import Approval, ApproverDelegation


def _local_date(value: datetime | date) -> date:
    if isinstance(value, datetime):
        return timezone.localtime(value).date()
    return value


def _buddhist_date_text(value: date) -> str:
    return f"{value.day:02d}/{value.month:02d}/{value.year + 543}"


def active_delegate(approver, on_date: date):
    delegation = ApproverDelegation.objects.filter(
        delegator=approver,
        start_date__lte=on_date,
        end_date__gte=on_date,
    ).select_related("delegate").first()
    return delegation.delegate if delegation else None


def effective_approver_ids(room, now: datetime) -> dict[str, set[int]]:
    on_date = _local_date(now)
    rows = list(room.approvers.select_related("user").all())
    primary_ids: set[int] = set()
    backup_ids: set[int] = set()
    for row in rows:
        if row.is_primary:
            delegate = active_delegate(row.user, on_date)
            primary_ids.add(delegate.pk if delegate else row.user_id)
        else:
            backup_ids.add(row.user_id)
    return {"primary_ids": primary_ids, "backup_ids": backup_ids}


def is_business_day(value: date) -> bool:
    from resources.models import Blackout

    if value.weekday() >= 5:
        return False
    zone = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(value, datetime.min.time()), zone)
    day_end = day_start + timedelta(days=1)
    return not Blackout.objects.filter(
        scope=Blackout.Scope.ALL,
        start_at__lt=day_end,
        end_at__gt=day_start,
    ).exists()


def sla_deadline(booking: Booking) -> datetime:
    cursor = booking.submitted_at or booking.created_at
    business_days = 0
    while business_days < 2:
        cursor += timedelta(days=1)
        if is_business_day(timezone.localtime(cursor).date()):
            business_days += 1
    return cursor


def series_expiry_deadline(series) -> datetime:
    earliest = series.occurrences.filter(
        request_status__in=[Booking.RequestStatus.PENDING, Booking.RequestStatus.APPROVED]
    ).aggregate(value=Min("start_at"))["value"]
    if earliest is None:
        earliest = series.occurrences.aggregate(value=Min("start_at"))["value"]
    if earliest is None:
        raise ValueError("ชุดการจองนี้ไม่มีรายการ")
    submitted_at = series.occurrences.order_by("submitted_at").values_list("submitted_at", flat=True).first()
    if submitted_at and earliest - submitted_at < timedelta(hours=24):
        return earliest
    return earliest - timedelta(hours=24)


def expiry_deadline(booking: Booking) -> datetime:
    if booking.series_id:
        return series_expiry_deadline(booking.series)
    submitted_at = booking.submitted_at or booking.created_at
    if booking.start_at - submitted_at < timedelta(hours=24):
        return booking.start_at
    return booking.start_at - timedelta(hours=24)


def can_decide(user, booking: Booking, now: datetime | None = None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    now = now or timezone.now()
    approvers = effective_approver_ids(booking.room, now)
    if user.pk in approvers["primary_ids"]:
        return True
    return user.pk in approvers["backup_ids"] and (
        booking.is_urgent or now >= sla_deadline(booking)
    )


def _on_behalf_of(user, booking: Booking, now: datetime):
    primary = (
        ResourceApprover.objects.filter(resource=booking.room, is_primary=True)
        .select_related("user")
        .first()
    )
    if not primary or primary.user_id == user.pk:
        return None
    delegate = active_delegate(primary.user, _local_date(now))
    if delegate and delegate.pk == user.pk:
        return primary.user
    return None


def _locked_pending(booking: Booking) -> Booking:
    locked = (
        Booking.objects.select_for_update()
        .select_related("room", "requester", "unit")
        .get(pk=booking.pk)
    )
    if locked.request_status != Booking.RequestStatus.PENDING:
        raise ValueError("คำขอนี้ถูกดำเนินการแล้ว")
    return locked


@transaction.atomic
def approve_booking(booking: Booking, user, now: datetime | None = None) -> Booking:
    from notifications.services import booking_summary, notify

    now = now or timezone.now()
    locked = _locked_pending(booking)
    if not can_decide(user, locked, now):
        raise PermissionError("คุณไม่มีสิทธิ์อนุมัติคำขอนี้")
    if now >= expiry_deadline(locked):
        raise ValueError("คำขอหมดอายุแล้ว")
    locked.request_status = Booking.RequestStatus.APPROVED
    locked.decision_reason = ""
    locked.save(update_fields=["request_status", "decision_reason", "updated_at"])
    Approval.objects.create(
        booking=locked,
        action=Approval.Action.APPROVED,
        acted_by=user,
        on_behalf_of=_on_behalf_of(user, locked, now),
    )
    recipients = [locked.requester, *locked.room.custodians.all()]
    notify(
        recipients,
        f"คำขอ {booking_summary(locked)} ได้รับการอนุมัติ",
        locked.get_absolute_url() if hasattr(locked, "get_absolute_url") else f"/bookings/{locked.pk}/",
        locked,
    )
    return locked


@transaction.atomic
def reject_booking(booking: Booking, user, reason: str, now: datetime | None = None) -> Booking:
    from notifications.services import booking_summary, notify

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("กรุณาระบุเหตุผล")
    now = now or timezone.now()
    locked = _locked_pending(booking)
    if not can_decide(user, locked, now):
        raise PermissionError("คุณไม่มีสิทธิ์ปฏิเสธคำขอนี้")
    if now >= expiry_deadline(locked):
        raise ValueError("คำขอหมดอายุแล้ว")
    locked.request_status = Booking.RequestStatus.REJECTED
    locked.decision_reason = reason
    locked.save(update_fields=["request_status", "decision_reason", "updated_at"])
    release_holds(locked)
    Approval.objects.create(
        booking=locked,
        action=Approval.Action.REJECTED,
        acted_by=user,
        on_behalf_of=_on_behalf_of(user, locked, now),
        reason=reason,
    )
    notify(
        [locked.requester],
        f"คำขอ {booking_summary(locked)} ถูกปฏิเสธ: {reason}",
        f"/bookings/{locked.pk}/",
        locked,
    )
    return locked


def pending_for(user, now: datetime | None = None) -> list[Booking]:
    now = now or timezone.now()
    bookings = (
        Booking.objects.filter(request_status=Booking.RequestStatus.PENDING)
        .select_related("room", "unit", "requester")
        .prefetch_related("equipment")
        .order_by("start_at")
    )
    if not getattr(user, "is_superuser", False):
        on_date = _local_date(now)
        delegated_primary_ids = ApproverDelegation.objects.filter(
            delegate=user,
            start_date__lte=on_date,
            end_date__gte=on_date,
        ).values_list("delegator_id", flat=True)
        room_ids = ResourceApprover.objects.filter(user=user).values_list("resource_id", flat=True)
        delegated_room_ids = ResourceApprover.objects.filter(
            user_id__in=delegated_primary_ids,
            is_primary=True,
        ).values_list("resource_id", flat=True)
        bookings = bookings.filter(room_id__in=set(room_ids) | set(delegated_room_ids))
    result = []
    seen_series = set()
    for booking in bookings:
        if can_decide(user, booking, now):
            if booking.series_id:
                if booking.series_id in seen_series:
                    continue
                seen_series.add(booking.series_id)
                booking.is_series_card = True
                booking.series_occurrences = list(
                    booking.series.occurrences.filter(request_status=Booking.RequestStatus.PENDING)
                    .select_related("room", "requester", "unit")
                    .order_by("start_at")
                )
                booking.series_last_at = booking.series_occurrences[-1].start_at
            booking.is_over_sla = now >= sla_deadline(booking)
            booking.expires_at = expiry_deadline(booking)
            booking.expires_in_hours = max(0, int((booking.expires_at - now).total_seconds() // 3600))
            approvers = effective_approver_ids(booking.room, now)
            booking.acting_as_backup = user.pk in approvers["backup_ids"] and user.pk not in approvers["primary_ids"]
            result.append(booking)
    return result


@transaction.atomic
def decide_series(series, user, action, excluded=None, reason_excluded="", reason_reject="", now=None):
    from bookings.series_services import series_ref
    from notifications.services import notify

    now = now or timezone.now()
    occurrences = list(
        Booking.objects.select_for_update()
        .filter(series=series, request_status=Booking.RequestStatus.PENDING)
        .select_related("room", "requester")
        .order_by("pk")
    )
    if not occurrences:
        raise ValueError("ชุดการจองนี้ถูกดำเนินการแล้ว")
    first = min(occurrences, key=lambda item: item.start_at)
    if not can_decide(user, first, now):
        raise PermissionError("คุณไม่มีสิทธิ์พิจารณาชุดการจองนี้")
    if now >= series_expiry_deadline(series):
        raise ValueError("ชุดการจองหมดอายุแล้ว")
    if action not in {"approve", "reject"}:
        raise ValidationError("การพิจารณาไม่ถูกต้อง")

    excluded_ids = {str(item) for item in (excluded or [])}
    occurrence_ids = {str(item.pk) for item in occurrences}
    if not excluded_ids.issubset(occurrence_ids):
        raise ValidationError("รายการที่ตัดออกไม่อยู่ในชุดนี้")
    reason_excluded = (reason_excluded or "").strip()
    reason_reject = (reason_reject or "").strip()
    if action == "approve" and excluded_ids and not reason_excluded:
        raise ValidationError("กรุณาระบุเหตุผลของครั้งที่ตัดออก")
    if action == "reject" and not reason_reject:
        raise ValidationError("กรุณาระบุเหตุผลปฏิเสธทั้งชุด")

    approved_count = rejected_count = 0
    for booking in occurrences:
        reject_this = action == "reject" or str(booking.pk) in excluded_ids
        if reject_this:
            reason = reason_reject if action == "reject" else reason_excluded
            booking.request_status = Booking.RequestStatus.REJECTED
            booking.decision_reason = reason
            booking.save(update_fields=["request_status", "decision_reason", "updated_at"])
            release_holds(booking)
            Approval.objects.create(
                booking=booking,
                action=Approval.Action.REJECTED,
                acted_by=user,
                on_behalf_of=_on_behalf_of(user, booking, now),
                reason=reason,
            )
            rejected_count += 1
        else:
            booking.request_status = Booking.RequestStatus.APPROVED
            booking.decision_reason = ""
            booking.save(update_fields=["request_status", "decision_reason", "updated_at"])
            Approval.objects.create(
                booking=booking,
                action=Approval.Action.APPROVED,
                acted_by=user,
                on_behalf_of=_on_behalf_of(user, booking, now),
            )
            approved_count += 1

    if action == "reject":
        text = f"ชุด {series_ref(series)} {series.room.code} ถูกปฏิเสธ {rejected_count} ครั้ง: {reason_reject}"
    else:
        text = f"ชุด {series_ref(series)} {series.room.code} อนุมัติ {approved_count} · ตัดออก {rejected_count} ครั้ง"
    recipients = [first.requester]
    if approved_count:
        recipients.extend(first.room.custodians.all())
    notify(recipients, text, f"/series/{series.pk}/", first)
    return {"approved": approved_count, "rejected": rejected_count}


def recent_rejection_reasons(user, limit: int = 10) -> list[str]:
    values = (
        Approval.objects.filter(acted_by=user, action=Approval.Action.REJECTED)
        .exclude(reason="")
        .order_by("-acted_at")
        .values_list("reason", flat=True)
    )
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
        if len(result) == limit:
            break
    return result


def has_approval_role(user, now: datetime | None = None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or ResourceApprover.objects.filter(user=user).exists():
        return True
    on_date = _local_date(now or timezone.now())
    return ApproverDelegation.objects.filter(
        delegate=user,
        start_date__lte=on_date,
        end_date__gte=on_date,
    ).exists()


@transaction.atomic
def create_delegation(delegator, delegate, start: date, end: date) -> ApproverDelegation:
    from notifications.services import notify

    if not ResourceApprover.objects.filter(user=delegator, is_primary=True).exists():
        raise PermissionError("เฉพาะผู้อนุมัติหลักเท่านั้นที่มอบหมายผู้รักษาการได้")
    if delegate.pk == delegator.pk:
        raise ValidationError("ไม่สามารถมอบหมายให้ตนเองได้")
    if end < start:
        raise ValidationError("วันสิ้นสุดต้องไม่อยู่ก่อนวันเริ่ม")
    if ApproverDelegation.objects.filter(
        delegator=delegator,
        start_date__lte=end,
        end_date__gte=start,
    ).exists():
        raise ValidationError("ช่วงวันที่มอบหมายทับซ้อนกับรายการเดิม")
    delegation = ApproverDelegation.objects.create(
        delegator=delegator,
        delegate=delegate,
        start_date=start,
        end_date=end,
    )
    notify(
        [delegate],
        f"คุณได้รับมอบหมายเป็นผู้รักษาการช่วง {_buddhist_date_text(start)}–{_buddhist_date_text(end)}",
        "/approvals/",
    )
    return delegation


def _approval_users(booking: Booking, now: datetime):
    ids = effective_approver_ids(booking.room, now)
    return get_user_model().objects.filter(pk__in=ids["primary_ids"] | ids["backup_ids"])


def run_scheduled_jobs(now: datetime | None = None) -> dict[str, int]:
    from bookings.series_services import series_ref
    from notifications.services import booking_summary, notify

    now = now or timezone.now()
    counts = {"expired": 0, "escalated": 0}
    pending_ids = list(
        Booking.objects.filter(request_status=Booking.RequestStatus.PENDING)
        .order_by("pk")
        .values_list("pk", flat=True)
    )
    processed_series = set()
    for booking_id in pending_ids:
        with transaction.atomic():
            booking = (
                Booking.objects.select_for_update()
                .select_related("room", "requester")
                .get(pk=booking_id)
            )
            if booking.request_status != Booking.RequestStatus.PENDING:
                continue
            if booking.series_id:
                if booking.series_id in processed_series:
                    continue
                processed_series.add(booking.series_id)
                occurrences = list(
                    Booking.objects.select_for_update()
                    .filter(series_id=booking.series_id, request_status=Booking.RequestStatus.PENDING)
                    .select_related("room", "requester", "series")
                    .order_by("pk")
                )
                if not occurrences:
                    continue
                first = min(occurrences, key=lambda item: item.start_at)
                if now >= series_expiry_deadline(first.series):
                    for occurrence in occurrences:
                        occurrence.request_status = Booking.RequestStatus.EXPIRED
                        occurrence.save(update_fields=["request_status", "updated_at"])
                        release_holds(occurrence)
                        Approval.objects.create(booking=occurrence, action=Approval.Action.EXPIRED)
                    recipients = [first.requester, *_approval_users(first, now)]
                    notify(
                        recipients,
                        f"ชุด {series_ref(first.series)} {first.room.code} หมดอายุแล้ว {len(occurrences)} ครั้ง",
                        f"/series/{first.series_id}/",
                        first,
                    )
                    counts["expired"] += len(occurrences)
                    continue
                to_escalate = [item for item in occurrences if item.sla_escalated_at is None]
                if now >= sla_deadline(first) and to_escalate:
                    for occurrence in to_escalate:
                        occurrence.sla_escalated_at = now
                        occurrence.save(update_fields=["sla_escalated_at", "updated_at"])
                    notify(
                        _approval_users(first, now),
                        f"ชุด {series_ref(first.series)} {first.room.code} เกิน SLA และเปิดสิทธิ์ผู้อนุมัติสำรองแล้ว",
                        f"/series/{first.series_id}/",
                        first,
                    )
                    counts["escalated"] += len(to_escalate)
                continue
            if now >= expiry_deadline(booking):
                booking.request_status = Booking.RequestStatus.EXPIRED
                booking.save(update_fields=["request_status", "updated_at"])
                release_holds(booking)
                Approval.objects.create(booking=booking, action=Approval.Action.EXPIRED)
                recipients = [booking.requester, *_approval_users(booking, now)]
                notify(
                    recipients,
                    f"คำขอ {booking_summary(booking)} หมดอายุแล้ว",
                    f"/bookings/{booking.pk}/",
                    booking,
                )
                counts["expired"] += 1
                continue
            if now >= sla_deadline(booking) and booking.sla_escalated_at is None:
                booking.sla_escalated_at = now
                booking.save(update_fields=["sla_escalated_at", "updated_at"])
                notify(
                    _approval_users(booking, now),
                    f"คำขอ {booking_summary(booking)} เกิน SLA และเปิดสิทธิ์ผู้อนุมัติสำรองแล้ว",
                    f"/bookings/{booking.pk}/",
                    booking,
                )
                counts["escalated"] += 1
    return counts

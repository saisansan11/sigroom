from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from approvals.models import Approval
from notifications.services import booking_summary, notify
from resources.models import Resource, ResourceRule

from .models import Booking, BookingAmendment, BookingResource
from .services import (
    BookingConflict,
    _urgent_deadline,
    approval_policy_for_values,
    compute_hold,
    validate_booking_window,
)


def _proposed_value(proposed, name, default=None):
    if isinstance(proposed, dict):
        if name in proposed:
            return proposed[name]
        prefixed = f"proposed_{name}"
        return proposed.get(prefixed, default)
    if hasattr(proposed, name):
        return getattr(proposed, name)
    return getattr(proposed, f"proposed_{name}", default)


def _final_values(booking: Booking, proposed) -> dict:
    room = _proposed_value(proposed, "room", booking.room)
    start_at = _proposed_value(proposed, "start_at", booking.start_at)
    end_at = _proposed_value(proposed, "end_at", booking.end_at)
    equipment = _proposed_value(proposed, "equipment", None)
    if equipment is None:
        equipment = list(booking.equipment.all())
    else:
        equipment = list({item.pk: item for item in equipment}.values())
    attendees = _proposed_value(proposed, "attendees", booking.attendees)
    has_external = _proposed_value(proposed, "has_external", booking.has_external_attendees)
    external_note = _proposed_value(proposed, "external_note", booking.external_attendees_note)
    reason = (_proposed_value(proposed, "reason", "") or "").strip()
    return {
        "room": room,
        "start_at": start_at,
        "end_at": end_at,
        "equipment": equipment,
        "attendees": attendees,
        "has_external": has_external,
        "external_note": external_note or "",
        "reason": reason,
    }


def evaluate_amendment_policy(booking: Booking, proposed) -> str:
    values = _final_values(booking, proposed)
    return approval_policy_for_values(values["room"], values["has_external"])


def available_amendment_rooms(
    booking: Booking,
    start_at: datetime,
    end_at: datetime,
    user,
    now: datetime | None = None,
):
    """คืนเฉพาะห้องปลายทางที่ว่างเมื่อไม่นับ hold ของการจองเดิม พร้อมห้องเดิมเสมอ"""
    now = now or timezone.now()
    room_ids = {booking.room_id}
    rooms = Resource.objects.filter(
        resource_type=Resource.Type.ROOM,
        status=Resource.Status.ACTIVE,
    ).select_related("rule")
    for room in rooms:
        if room.pk == booking.room_id:
            continue
        if validate_booking_window(room, start_at, end_at, user, now):
            continue
        hold = compute_hold(room, start_at, end_at)
        occupied = BookingResource.objects.filter(
            resource=room,
            released_at__isnull=True,
            hold__overlap=hold,
        ).exclude(booking=booking).exists()
        if not occupied:
            room_ids.add(room.pk)
    return Resource.objects.filter(pk__in=room_ids).select_related("rule").order_by("code")


def amendment_ref(amendment: BookingAmendment) -> str:
    return "AM-" + str(amendment.pk).replace("-", "")[:4].upper()


def amendment_expiry_deadline(amendment: BookingAmendment) -> datetime:
    proposed_start = amendment.proposed_start_at or amendment.booking.start_at
    earliest = min(amendment.booking.start_at, proposed_start)
    submitted_at = amendment.submitted_at
    if earliest - submitted_at < timedelta(hours=24):
        return earliest
    return earliest - timedelta(hours=24)


def _amendment_approver_users(room: Resource, now: datetime, *, include_backup=False):
    from approvals.services import effective_approver_ids

    ids = effective_approver_ids(room, now)
    recipient_ids = set(ids["primary_ids"])
    if include_backup:
        recipient_ids.update(ids["backup_ids"])
    return get_user_model().objects.filter(pk__in=recipient_ids)


def _create_amendment_holds(amendment: BookingAmendment, values: dict) -> list[BookingResource]:
    holds = []
    for resource in [values["room"], *values["equipment"]]:
        try:
            with transaction.atomic():
                holds.append(
                    BookingResource.objects.create(
                        booking=amendment.booking,
                        amendment=amendment,
                        resource=resource,
                        hold=compute_hold(resource, values["start_at"], values["end_at"]),
                    )
                )
        except IntegrityError as exc:
            if "excl_overlapping_holds" in str(exc):
                raise BookingConflict(resource) from exc
            raise
    return holds


@transaction.atomic
def submit_amendment(booking: Booking, user, proposed, now: datetime | None = None) -> BookingAmendment:
    now = now or timezone.now()
    locked = (
        Booking.objects.select_for_update()
        .select_related("room", "requester", "unit")
        .prefetch_related("equipment")
        .get(pk=booking.pk)
    )
    if locked.requester_id != getattr(user, "pk", None) and not getattr(user, "is_superuser", False):
        raise PermissionError("คุณไม่มีสิทธิ์ขอแก้ไขการจองนี้")
    if locked.request_status != Booking.RequestStatus.APPROVED or locked.usage_status != Booking.UsageStatus.UPCOMING:
        raise ValueError("ขอแก้ไขได้เฉพาะการจองที่อนุมัติแล้วและยังไม่เริ่มใช้งาน")
    cutoff_hours = getattr(getattr(locked.room, "rule", None), "cancel_cutoff_hours", 4)
    if locked.start_at - now < timedelta(hours=cutoff_hours):
        raise PermissionError("พ้นเวลาขอแก้ไขด้วยตนเอง กรุณาติดต่อเจ้าหน้าที่ดูแลห้อง")
    if locked.amendments.filter(status=BookingAmendment.Status.PENDING).exists():
        raise ValidationError("การจองนี้มีคำขอแก้ไขรออนุมัติอยู่แล้ว")

    values = _final_values(locked, proposed)
    if any(
        item.resource_type != Resource.Type.EQUIPMENT or item.status != Resource.Status.ACTIVE
        for item in values["equipment"]
    ):
        raise ValidationError("อุปกรณ์ส่วนกลางที่เลือกไม่ถูกต้องหรือไม่ได้เปิดใช้งาน")
    errors = validate_booking_window(values["room"], values["start_at"], values["end_at"], user, now)
    if errors:
        raise ValidationError(errors)
    equipment_ids = {item.pk for item in values["equipment"]}
    current_equipment_ids = set(locked.equipment.values_list("pk", flat=True))
    changed = any(
        [
            values["room"].pk != locked.room_id,
            values["start_at"] != locked.start_at,
            values["end_at"] != locked.end_at,
            equipment_ids != current_equipment_ids,
            values["attendees"] != locked.attendees,
            values["has_external"] != locked.has_external_attendees,
            values["external_note"] != locked.external_attendees_note,
        ]
    )
    if not changed:
        raise ValidationError("กรุณาแก้ไขอย่างน้อย 1 รายการ")

    amendment = BookingAmendment.objects.create(
        booking=locked,
        submitted_by=user,
        base_revision=locked.revision,
        proposed_room=values["room"] if values["room"].pk != locked.room_id else None,
        proposed_start_at=values["start_at"] if values["start_at"] != locked.start_at else None,
        proposed_end_at=values["end_at"] if values["end_at"] != locked.end_at else None,
        proposed_attendees=values["attendees"] if values["attendees"] != locked.attendees else None,
        proposed_has_external=(
            values["has_external"] if values["has_external"] != locked.has_external_attendees else None
        ),
        proposed_external_note=values["external_note"],
        reason=values["reason"],
    )
    BookingAmendment.objects.filter(pk=amendment.pk).update(submitted_at=now)
    amendment.submitted_at = now
    amendment.proposed_equipment.set(values["equipment"])
    _create_amendment_holds(amendment, values)
    policy = evaluate_amendment_policy(locked, values)
    amendment.is_urgent = policy == ResourceRule.ApprovalPolicy.REQUIRED and min(
        locked.start_at, values["start_at"]
    ) < _urgent_deadline(now)
    amendment.save(update_fields=["is_urgent"])

    if policy == ResourceRule.ApprovalPolicy.AUTO:
        return apply_amendment(amendment, user, None, now)

    summary = booking_summary(locked)
    notify(
        _amendment_approver_users(values["room"], now, include_backup=amendment.is_urgent),
        f"มีคำขอแก้ไข {amendment_ref(amendment)} รออนุมัติ: {summary}",
        "/approvals/",
        locked,
    )
    if values["room"].pk != locked.room_id and values["room"].owner_unit_id != locked.room.owner_unit_id:
        notify(
            _amendment_approver_users(locked.room, now),
            f"แจ้งเพื่อทราบ: {summary} ขอเปลี่ยนออกจากห้อง {locked.room.code}",
            f"/bookings/{locked.pk}/",
            locked,
        )
    return amendment


@transaction.atomic
def apply_amendment(
    amendment: BookingAmendment,
    acted_by,
    on_behalf_of=None,
    now: datetime | None = None,
) -> BookingAmendment:
    now = now or timezone.now()
    locked_amendment = (
        BookingAmendment.objects.select_for_update()
        .select_related("booking", "booking__room", "submitted_by")
        .prefetch_related("proposed_equipment")
        .get(pk=amendment.pk)
    )
    if locked_amendment.status != BookingAmendment.Status.PENDING:
        raise ValueError("คำขอแก้ไขนี้ถูกดำเนินการแล้ว")
    booking = (
        Booking.objects.select_for_update()
        .select_related("room", "requester")
        .get(pk=locked_amendment.booking_id)
    )
    if (
        booking.request_status != Booking.RequestStatus.APPROVED
        or booking.usage_status != Booking.UsageStatus.UPCOMING
        or booking.revision != locked_amendment.base_revision
    ):
        raise ValueError("ข้อมูลการจองเปลี่ยนไปแล้ว กรุณาถอนและยื่นใหม่")

    old_room = booking.room
    final_room = locked_amendment.proposed_room or booking.room
    final_start = locked_amendment.proposed_start_at or booking.start_at
    final_end = locked_amendment.proposed_end_at or booking.end_at
    final_equipment = list(locked_amendment.proposed_equipment.all())
    final_attendees = (
        locked_amendment.proposed_attendees
        if locked_amendment.proposed_attendees is not None
        else booking.attendees
    )
    final_has_external = (
        locked_amendment.proposed_has_external
        if locked_amendment.proposed_has_external is not None
        else booking.has_external_attendees
    )

    expected_resource_ids = {final_room.pk, *(item.pk for item in final_equipment)}
    active_amendment_holds = locked_amendment.holds.filter(released_at__isnull=True)
    if set(active_amendment_holds.values_list("resource_id", flat=True)) != expected_resource_ids:
        raise ValueError("ช่วงถือครองปลายทางไม่ครบ ระบบยังไม่เปลี่ยนการจองเดิม")

    booking.holds.filter(amendment__isnull=True, released_at__isnull=True).update(released_at=now)
    active_amendment_holds.update(amendment=None)
    booking.room = final_room
    booking.start_at = final_start
    booking.end_at = final_end
    booking.attendees = final_attendees
    booking.has_external_attendees = final_has_external
    booking.external_attendees_note = locked_amendment.proposed_external_note
    booking.revision += 1
    booking.save(
        update_fields=[
            "room", "start_at", "end_at", "attendees", "has_external_attendees",
            "external_attendees_note", "revision", "updated_at",
        ]
    )
    booking.equipment.set(final_equipment)
    locked_amendment.status = BookingAmendment.Status.APPROVED
    locked_amendment.decision_reason = ""
    locked_amendment.decided_at = now
    locked_amendment.save(update_fields=["status", "decision_reason", "decided_at"])
    Approval.objects.create(
        booking=booking,
        amendment=locked_amendment,
        action=Approval.Action.APPROVED,
        acted_by=acted_by,
        on_behalf_of=on_behalf_of,
    )
    recipients = {item.pk: item for item in [booking.requester, *old_room.custodians.all(), *final_room.custodians.all()]}
    notify(
        recipients.values(),
        f"คำขอแก้ไข {amendment_ref(locked_amendment)} ของ {booking_summary(booking)} ได้รับการอนุมัติ",
        f"/bookings/{booking.pk}/",
        booking,
    )
    return locked_amendment


def _release_amendment_holds(amendment: BookingAmendment, now: datetime) -> int:
    return amendment.holds.filter(released_at__isnull=True).update(released_at=now)


@transaction.atomic
def withdraw_amendment(
    amendment: BookingAmendment,
    user,
    reason: str = "",
    now: datetime | None = None,
) -> BookingAmendment:
    now = now or timezone.now()
    locked = BookingAmendment.objects.select_for_update().select_related("booking", "submitted_by").get(pk=amendment.pk)
    if locked.status != BookingAmendment.Status.PENDING:
        raise ValueError("คำขอแก้ไขนี้ถูกดำเนินการแล้ว")
    allowed = locked.submitted_by_id == getattr(user, "pk", None) or getattr(user, "is_superuser", False)
    if not allowed and reason == "ถอนอัตโนมัติ: การจองถูกบังคับย้าย":
        from .preemption_services import can_preempt

        allowed = can_preempt(user, locked.booking, now)
    if not allowed:
        raise PermissionError("คุณไม่มีสิทธิ์ถอนคำขอแก้ไขนี้")
    _release_amendment_holds(locked, now)
    locked.status = BookingAmendment.Status.WITHDRAWN
    locked.decision_reason = (reason or "").strip()
    locked.decided_at = now
    locked.save(update_fields=["status", "decision_reason", "decided_at"])
    Approval.objects.create(
        booking=locked.booking,
        amendment=locked,
        action=Approval.Action.WITHDRAWN,
        acted_by=user,
        reason=locked.decision_reason,
    )
    notify(
        [locked.submitted_by],
        f"ถอนคำขอแก้ไข {amendment_ref(locked)} แล้ว",
        f"/bookings/{locked.booking_id}/",
        locked.booking,
    )
    return locked


@transaction.atomic
def reject_amendment(
    amendment: BookingAmendment,
    user,
    reason: str,
    now: datetime | None = None,
) -> BookingAmendment:
    from approvals.services import can_decide, on_behalf_of_for

    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("กรุณาระบุเหตุผล")
    now = now or timezone.now()
    locked = BookingAmendment.objects.select_for_update().select_related("booking", "submitted_by").get(pk=amendment.pk)
    if locked.status != BookingAmendment.Status.PENDING:
        raise ValueError("คำขอแก้ไขนี้ถูกดำเนินการแล้ว")
    if not can_decide(user, locked, now):
        raise PermissionError("คุณไม่มีสิทธิ์ปฏิเสธคำขอแก้ไขนี้")
    if now >= amendment_expiry_deadline(locked):
        raise ValueError("คำขอแก้ไขหมดอายุแล้ว")
    _release_amendment_holds(locked, now)
    locked.status = BookingAmendment.Status.REJECTED
    locked.decision_reason = reason
    locked.decided_at = now
    locked.save(update_fields=["status", "decision_reason", "decided_at"])
    Approval.objects.create(
        booking=locked.booking,
        amendment=locked,
        action=Approval.Action.REJECTED,
        acted_by=user,
        on_behalf_of=on_behalf_of_for(user, locked, now),
        reason=reason,
    )
    notify(
        [locked.submitted_by],
        f"คำขอแก้ไข {amendment_ref(locked)} ถูกปฏิเสธ: {reason}",
        f"/bookings/{locked.booking_id}/",
        locked.booking,
    )
    return locked


@transaction.atomic
def expire_amendment(amendment: BookingAmendment, now: datetime | None = None) -> BookingAmendment:
    now = now or timezone.now()
    locked = BookingAmendment.objects.select_for_update().select_related("booking", "submitted_by").get(pk=amendment.pk)
    if locked.status != BookingAmendment.Status.PENDING:
        return locked
    _release_amendment_holds(locked, now)
    locked.status = BookingAmendment.Status.EXPIRED
    locked.decision_reason = "หมดอายุตามกำหนด"
    locked.decided_at = now
    locked.save(update_fields=["status", "decision_reason", "decided_at"])
    Approval.objects.create(
        booking=locked.booking,
        amendment=locked,
        action=Approval.Action.EXPIRED,
        reason=locked.decision_reason,
    )
    notify(
        [locked.submitted_by],
        f"คำขอแก้ไข {amendment_ref(locked)} หมดอายุแล้ว การจองเดิมยังคงอยู่",
        f"/bookings/{locked.booking_id}/",
        locked.booking,
    )
    return locked

from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import Unit
from approvals.services import effective_approver_ids
from notifications.services import booking_summary, notify
from resources.models import Resource, ResourceRule

from .amendment_services import withdraw_amendment
from .models import Booking, BookingAmendment, BookingResource, Preemption
from .services import (
    approval_policy_for_values,
    compute_hold,
    place_holds,
    release_holds,
    validate_booking_window,
)


@dataclass(frozen=True)
class ReplacementOption:
    room: Resource
    group: int
    approval_label: str


def can_preempt(user, booking: Booking, now: datetime | None = None) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser:
        return True
    approvers = effective_approver_ids(booking.room, now or timezone.now())
    return user.pk in approvers["primary_ids"]


def _replacement_group(room: Resource, booking: Booking, actor, now: datetime) -> int:
    policy = approval_policy_for_values(room, booking.has_external_attendees)
    if policy == ResourceRule.ApprovalPolicy.AUTO:
        return 1
    if actor.pk in effective_approver_ids(room, now)["primary_ids"]:
        return 2
    return 3


def replacement_options(
    booking: Booking,
    actor,
    now: datetime | None = None,
) -> list[ReplacementOption]:
    now = now or timezone.now()
    groups: dict[int, list[ReplacementOption]] = {1: [], 2: [], 3: []}
    rooms = (
        Resource.objects.filter(
            resource_type=Resource.Type.ROOM,
            status=Resource.Status.ACTIVE,
        )
        .exclude(pk=booking.room_id)
        .select_related("rule", "owner_unit")
        .order_by("code")
    )
    for room in rooms:
        if room.capacity and room.capacity < booking.attendees:
            continue
        if validate_booking_window(room, booking.start_at, booking.end_at, booking.requester, now):
            continue
        hold = compute_hold(room, booking.start_at, booking.end_at)
        if BookingResource.objects.filter(
            resource=room,
            released_at__isnull=True,
            hold__overlap=hold,
        ).exclude(booking=booking).exists():
            continue
        group = _replacement_group(room, booking, actor, now)
        label = "อนุมัติทันที" if group in {1, 2} else "ต้องอนุมัติ · เข้าคิวเร่งด่วน"
        groups[group].append(ReplacementOption(room, group, label))
    return [*groups[1][:3], *groups[2][:3], *groups[3][:3]]


def _incoming_value(data: dict, name: str, default=None):
    value = data.get(name, default)
    return value if value is not None else default


def _copy_replacement(displaced: Booking, room: Resource, status: str, now: datetime) -> Booking:
    replacement = Booking.objects.create(
        room=room,
        requester=displaced.requester,
        unit=displaced.unit,
        responsible_name=displaced.responsible_name,
        responsible_phone=displaced.responsible_phone,
        title=displaced.title,
        purpose=displaced.purpose,
        start_at=displaced.start_at,
        end_at=displaced.end_at,
        attendees=displaced.attendees,
        attendee_level=displaced.attendee_level,
        layout=displaced.layout,
        fixed_equipment_needed=displaced.fixed_equipment_needed,
        has_external_attendees=displaced.has_external_attendees,
        external_attendees_note=displaced.external_attendees_note,
        visibility=displaced.visibility,
        note=displaced.note,
        request_status=status,
        usage_status=Booking.UsageStatus.UPCOMING,
        submitted_at=now,
        is_urgent=status == Booking.RequestStatus.PENDING,
    )
    equipment = list(displaced.equipment.all())
    replacement.equipment.set(equipment)
    place_holds(replacement, equipment)
    return replacement


@transaction.atomic
def execute_preemption(
    booking: Booking,
    actor,
    reason: str,
    reference_no: str,
    incoming_data: dict,
    replacement_room: Resource | None,
    now: datetime | None = None,
) -> Preemption:
    now = now or timezone.now()
    reason = (reason or "").strip()
    reference_no = (reference_no or "").strip()
    if not reason:
        raise ValidationError("กรุณาระบุเหตุผลการบังคับย้าย")
    if not reference_no:
        raise ValidationError("กรุณาระบุเลขอ้างอิงคำสั่ง/หนังสือ")

    displaced = (
        Booking.objects.select_for_update()
        .select_related("room", "requester", "unit")
        .prefetch_related("equipment")
        .get(pk=booking.pk)
    )
    if not can_preempt(actor, displaced, now):
        raise PermissionError("คุณไม่มีสิทธิ์บังคับย้ายการจองนี้")
    if displaced.request_status != Booking.RequestStatus.APPROVED or displaced.usage_status != Booking.UsageStatus.UPCOMING:
        raise ValueError("บังคับย้ายได้เฉพาะการจองที่อนุมัติแล้วและยังไม่เริ่มใช้งาน")

    start_at = _incoming_value(incoming_data, "start_at", displaced.start_at)
    end_at = _incoming_value(incoming_data, "end_at", displaced.end_at)
    if end_at <= displaced.start_at or start_at >= displaced.end_at:
        raise ValidationError("เวลาของงานที่เข้าแทนต้องซ้อนกับการจองเดิม")
    if end_at <= start_at:
        raise ValidationError("เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม")
    unit = _incoming_value(incoming_data, "unit")
    if isinstance(unit, int):
        unit = Unit.objects.get(pk=unit)
    required_values = {
        "title": (_incoming_value(incoming_data, "title", "") or "").strip(),
        "responsible_name": (_incoming_value(incoming_data, "responsible_name", "") or "").strip(),
        "responsible_phone": (_incoming_value(incoming_data, "responsible_phone", "") or "").strip(),
    }
    if not unit or not all(required_values.values()):
        raise ValidationError("กรุณากรอกชื่องาน หน่วย ผู้รับผิดชอบ และโทรศัพท์ให้ครบ")

    pending = displaced.amendments.filter(status=BookingAmendment.Status.PENDING).first()
    if pending:
        withdraw_amendment(
            pending,
            actor,
            "ถอนอัตโนมัติ: การจองถูกบังคับย้าย",
            now,
        )
    release_holds(displaced)
    displaced.usage_status = Booking.UsageStatus.DISPLACED
    displaced.save(update_fields=["usage_status", "updated_at"])

    incoming = Booking.objects.create(
        room=displaced.room,
        requester=actor,
        unit=unit,
        responsible_name=required_values["responsible_name"],
        responsible_phone=required_values["responsible_phone"],
        title=required_values["title"],
        purpose=_incoming_value(incoming_data, "purpose", Booking.Purpose.OTHER),
        start_at=start_at,
        end_at=end_at,
        attendees=_incoming_value(incoming_data, "attendees", 1),
        visibility=_incoming_value(incoming_data, "visibility", Booking.Visibility.RESTRICTED),
        request_status=Booking.RequestStatus.APPROVED,
        usage_status=Booking.UsageStatus.UPCOMING,
        submitted_at=now,
    )
    place_holds(incoming)

    replacement = None
    if replacement_room is not None:
        choices = {item.room.pk: item for item in replacement_options(displaced, actor, now)}
        option = choices.get(replacement_room.pk)
        if option is None:
            raise ValidationError("ห้องทดแทนที่เลือกไม่ว่างหรือไม่ผ่านเงื่อนไข")
        status = (
            Booking.RequestStatus.APPROVED
            if option.group in {1, 2}
            else Booking.RequestStatus.PENDING
        )
        replacement = _copy_replacement(displaced, replacement_room, status, now)
        if status == Booking.RequestStatus.PENDING:
            ids = effective_approver_ids(replacement_room, now)
            from accounts.models import User

            notify(
                User.objects.filter(pk__in=ids["primary_ids"] | ids["backup_ids"]),
                f"มีคำขอห้องทดแทนเร่งด่วนรออนุมัติ: {booking_summary(replacement)}",
                f"/bookings/{replacement.pk}/",
                replacement,
            )

    preemption = Preemption.objects.create(
        displaced=displaced,
        incoming=incoming,
        replacement=replacement,
        ordered_by=actor,
        ordered_by_position=(actor.position or ("ผู้ดูแลระบบ" if actor.is_superuser else "ผู้อนุมัติห้อง")),
        reference_no=reference_no,
        reason=reason,
    )
    Preemption.objects.filter(pk=preemption.pk).update(created_at=now)
    preemption.created_at = now
    replacement_text = (
        f" · ห้องทดแทน {booking_summary(replacement)}"
        if replacement
        else " · ไม่มีห้องทดแทน"
    )
    notify(
        [displaced.requester],
        f"การจอง {booking_summary(displaced)} ถูกย้ายตามคำสั่ง {reference_no} โดย {preemption.ordered_by_position}{replacement_text}",
        f"/bookings/{displaced.pk}/",
        displaced,
    )
    custodians = [*displaced.room.custodians.all()]
    if replacement:
        custodians.extend(replacement.room.custodians.all())
    notify(
        custodians,
        f"ดำเนินการบังคับย้ายตามคำสั่ง {reference_no} แล้ว",
        f"/bookings/{displaced.pk}/",
        displaced,
    )
    return preemption


@transaction.atomic
def acknowledge(preemption: Preemption, user, now: datetime | None = None) -> Preemption:
    now = now or timezone.now()
    locked = Preemption.objects.select_for_update().select_related("displaced", "ordered_by").get(pk=preemption.pk)
    if locked.displaced.requester_id != getattr(user, "pk", None):
        raise PermissionError("เฉพาะผู้จองเดิมเท่านั้นที่กดรับทราบได้")
    if locked.acknowledged_at is not None or locked.deemed_acknowledged:
        return locked
    locked.acknowledged_at = now
    locked.save(update_fields=["acknowledged_at"])
    notify(
        [locked.ordered_by],
        f"ผู้จองเดิมรับทราบคำสั่ง {locked.reference_no} แล้ว",
        f"/bookings/{locked.displaced_id}/",
        locked.displaced,
    )
    return locked

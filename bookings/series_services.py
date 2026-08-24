from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from resources.models import Resource, ResourceRule
from resources.services import active_blackouts

from .models import Booking, BookingResource, BookingSeries, SeriesSkip
from .services import (
    BookingConflict,
    _urgent_deadline,
    approval_policy_for,
    calendar_label,
    cancel_booking,
    compute_hold,
    place_holds,
    validate_booking_window,
)


@dataclass(frozen=True)
class SeriesPreviewItem:
    index: int
    occur_date: date
    start_at: datetime
    end_at: datetime
    status: str
    reason: str = ""

    @property
    def is_free(self) -> bool:
        return self.status == "free"


@dataclass(frozen=True)
class SeriesPreview:
    items: list[SeriesPreviewItem]

    @property
    def free_count(self) -> int:
        return sum(item.status == "free" for item in self.items)

    @property
    def conflict_count(self) -> int:
        return sum(item.status == "conflict" for item in self.items)

    @property
    def skipped_count(self) -> int:
        return sum(item.status == "blackout" for item in self.items)


def _value(params, name, default=None):
    if isinstance(params, dict):
        return params.get(name, default)
    return getattr(params, name, default)


def _as_date(value) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def generate_occurrence_dates(series_params, rule: ResourceRule) -> list[date]:
    if not rule.allow_series:
        raise ValidationError("ห้องนี้ไม่อนุญาตให้จองเป็นชุด")
    max_count = rule.max_series_occurrences
    requested_count = _value(series_params, "requested_count")
    requested_count = int(requested_count) if requested_count else None
    if requested_count and requested_count > max_count:
        raise ValidationError(f"ห้องนี้จองเป็นชุดได้ไม่เกิน {max_count} ครั้ง")

    freq = _value(series_params, "freq")
    start_date = _as_date(_value(series_params, "start_date"))
    end_date = _as_date(_value(series_params, "end_date"))
    if not start_date:
        raise ValidationError("กรุณาระบุวันที่เริ่มของชุด")
    if end_date and end_date < start_date:
        raise ValidationError("วันที่สิ้นสุดชุดต้องไม่อยู่ก่อนวันที่เริ่ม")
    if end_date and (end_date - start_date).days > 3660:
        raise ValidationError("ช่วงวันที่ของชุดยาวเกินไป")

    if freq == BookingSeries.Frequency.CUSTOM:
        dates = sorted({_as_date(item) for item in _value(series_params, "custom_dates", []) if item})
        dates = [item for item in dates if item >= start_date and (not end_date or item <= end_date)]
        if requested_count:
            dates = dates[:requested_count]
    else:
        weekdays = set(range(5)) if freq == BookingSeries.Frequency.WORKDAYS else {
            int(item) for item in _value(series_params, "weekdays", [])
        }
        if freq not in {BookingSeries.Frequency.WEEKLY, BookingSeries.Frequency.WORKDAYS}:
            raise ValidationError("รูปแบบชุดการจองไม่ถูกต้อง")
        if not weekdays or any(item not in range(7) for item in weekdays):
            raise ValidationError("กรุณาเลือกวันในสัปดาห์อย่างน้อย 1 วัน")
        if not end_date and not requested_count:
            raise ValidationError("กรุณาระบุวันที่สิ้นสุดหรือจำนวนครั้ง")
        dates = []
        cursor = start_date
        while (not end_date or cursor <= end_date) and (not requested_count or len(dates) < requested_count):
            if cursor.weekday() in weekdays:
                dates.append(cursor)
                if len(dates) > max_count:
                    break
            cursor += timedelta(days=1)

    if not dates:
        raise ValidationError("ไม่พบวันที่สำหรับชุดการจอง")
    if len(dates) > max_count:
        raise ValidationError(f"ห้องนี้จองเป็นชุดได้ไม่เกิน {max_count} ครั้ง")
    return dates


def _at(occur_date: date, value, zone) -> datetime:
    return timezone.make_aware(datetime.combine(occur_date, value), zone)


def _equipment_for(booking_template) -> list[Resource]:
    if hasattr(booking_template, "_series_equipment"):
        return list(booking_template._series_equipment)
    if booking_template.pk:
        return list(booking_template.equipment.all())
    return []


def _conflict_reason(room, equipment, start_at, end_at, user) -> str:
    for resource in [room, *equipment]:
        hold = compute_hold(resource, start_at, end_at)
        collision = (
            BookingResource.objects.filter(resource=resource, released_at__isnull=True, hold__overlap=hold)
            .select_related("booking", "booking__room", "booking__unit", "booking__requester")
            .first()
        )
        if collision:
            if resource.pk == room.pk:
                return calendar_label(user, collision.booking)
            return f"อุปกรณ์ส่วนกลางไม่ว่าง: {resource.code} {resource.name}"
    return ""


def preview_series(room, series_params, booking_template, user, now=None) -> SeriesPreview:
    now = now or timezone.now()
    dates = generate_occurrence_dates(series_params, room.rule)
    zone = timezone.get_current_timezone()
    time_start = _value(series_params, "time_start")
    time_end = _value(series_params, "time_end")
    equipment = _equipment_for(booking_template)
    items: list[SeriesPreviewItem] = []
    for index, occur_date in enumerate(dates, start=1):
        start_at = _at(occur_date, time_start, zone)
        end_at = _at(occur_date, time_end, zone)
        blackouts = active_blackouts(room, start_at, end_at)
        if blackouts:
            items.append(SeriesPreviewItem(index, occur_date, start_at, end_at, "blackout", blackouts[0].title))
            continue
        errors = validate_booking_window(room, start_at, end_at, user, now=now)
        if errors:
            items.append(SeriesPreviewItem(index, occur_date, start_at, end_at, "conflict", " · ".join(errors)))
            continue
        reason = _conflict_reason(room, equipment, start_at, end_at, user)
        if reason:
            items.append(SeriesPreviewItem(index, occur_date, start_at, end_at, "conflict", reason))
        else:
            items.append(SeriesPreviewItem(index, occur_date, start_at, end_at, "free"))
    return SeriesPreview(items)


def series_ref(series: BookingSeries) -> str:
    return "SR-" + str(series.pk).replace("-", "")[:4].upper()


BOOKING_COPY_FIELDS = (
    "unit",
    "responsible_name",
    "responsible_phone",
    "title",
    "purpose",
    "attendees",
    "attendee_level",
    "layout",
    "fixed_equipment_needed",
    "has_external_attendees",
    "external_attendees_note",
    "visibility",
    "note",
)


@transaction.atomic
def create_series(room, series_params, booking_template, user, mode="only_free", now=None) -> BookingSeries:
    from accounts.models import User
    from approvals.models import Approval
    from approvals.services import effective_approver_ids
    from notifications.services import notify

    if mode != "only_free":
        raise ValidationError("M4 รองรับการจองเฉพาะครั้งที่ว่าง")
    now = now or timezone.now()
    preview = preview_series(room, series_params, booking_template, user, now)
    if not preview.free_count:
        raise ValidationError("ไม่มีครั้งที่ว่างให้สร้างชุดการจอง")
    dates = [item.occur_date for item in preview.items]
    series = BookingSeries.objects.create(
        room=room,
        created_by=user,
        unit=booking_template.unit,
        freq=_value(series_params, "freq"),
        weekdays=[int(item) for item in _value(series_params, "weekdays", [])],
        custom_dates=[str(item) for item in _value(series_params, "custom_dates", [])],
        start_date=min(dates),
        end_date=_as_date(_value(series_params, "end_date")),
        requested_count=_value(series_params, "requested_count"),
        time_start=_value(series_params, "time_start"),
        time_end=_value(series_params, "time_end"),
    )
    equipment = _equipment_for(booking_template)
    policy = approval_policy_for(booking_template)
    free_items = [item for item in preview.items if item.is_free]
    is_urgent = policy == ResourceRule.ApprovalPolicy.REQUIRED and free_items[0].start_at < _urgent_deadline(now)
    created: list[Booking] = []
    preview_free_dates = {str(item) for item in _value(series_params, "preview_free_dates", [])}
    for item in preview.items:
        if item.status == "blackout":
            SeriesSkip.objects.create(
                series=series,
                occur_date=item.occur_date,
                kind=SeriesSkip.Kind.BLACKOUT,
                reason=item.reason[:200],
            )
            continue
        if item.status == "conflict":
            SeriesSkip.objects.create(
                series=series,
                occur_date=item.occur_date,
                kind=(
                    SeriesSkip.Kind.CONFLICT_AT_SUBMIT
                    if str(item.occur_date) in preview_free_dates
                    else SeriesSkip.Kind.CONFLICT
                ),
                reason=item.reason[:200],
            )
            continue
        values = {field: getattr(booking_template, field) for field in BOOKING_COPY_FIELDS}
        try:
            with transaction.atomic():
                booking = Booking.objects.create(
                    room=room,
                    requester=user,
                    start_at=item.start_at,
                    end_at=item.end_at,
                    request_status=(
                        Booking.RequestStatus.APPROVED
                        if policy == ResourceRule.ApprovalPolicy.AUTO
                        else Booking.RequestStatus.PENDING
                    ),
                    submitted_at=now,
                    is_urgent=is_urgent,
                    series=series,
                    series_index=item.index,
                    **values,
                )
                booking.equipment.set(equipment)
                place_holds(booking, equipment)
        except BookingConflict as exc:
            SeriesSkip.objects.create(
                series=series,
                occur_date=item.occur_date,
                kind=SeriesSkip.Kind.CONFLICT_AT_SUBMIT,
                reason=str(exc)[:200],
            )
            continue
        Approval.objects.create(booking=booking, action=Approval.Action.SUBMITTED)
        created.append(booking)
    if not created:
        raise ValidationError("ไม่มีครั้งที่ว่างให้สร้างชุดการจอง")

    url = f"/series/{series.pk}/"
    state = "อนุมัติอัตโนมัติ" if policy == ResourceRule.ApprovalPolicy.AUTO else "รออนุมัติ"
    notify(
        [user],
        f"สร้างชุด {series_ref(series)} {room.code} สำเร็จ {len(created)} ครั้ง · {state}",
        url,
    )
    if policy == ResourceRule.ApprovalPolicy.REQUIRED:
        ids = effective_approver_ids(room, now)
        recipient_ids = set(ids["primary_ids"])
        if is_urgent:
            recipient_ids.update(ids["backup_ids"])
        notify(
            User.objects.filter(pk__in=recipient_ids),
            f"มีชุด {series_ref(series)} {room.code} รออนุมัติ {len(created)} ครั้ง",
            url,
        )
    return series


def cancel_remaining(series: BookingSeries, user, now=None) -> dict:
    if series.created_by_id != getattr(user, "pk", None) and not getattr(user, "is_superuser", False):
        raise PermissionError("คุณไม่มีสิทธิ์ยกเลิกชุดการจองนี้")
    now = now or timezone.now()
    cancelled = 0
    skipped = []
    occurrences = series.occurrences.filter(
        start_at__gt=now,
        request_status__in=Booking.HOLDING_STATUSES,
    ).select_related("room", "room__rule")
    for booking in occurrences:
        try:
            cancel_booking(booking, user, now=now)
        except (PermissionError, ValueError) as exc:
            skipped.append({"booking": booking, "reason": str(exc)})
        else:
            cancelled += 1
    return {"cancelled": cancelled, "skipped": skipped}

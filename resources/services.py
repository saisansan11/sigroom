import logging
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from audit.services import audit

from .models import Blackout, Resource, ResourceOutage, ResourcePhoto

logger = logging.getLogger(__name__)


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
    audit(user, "resources.resourceoutage", outage.pk, "outage_created", after={"resource_id": resource.pk, "start_at": start, "end_at": end, "reason": reason})
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
    audit(user, "resources.resourceoutage", outage.pk, "outage_ended", after={"ended_early_at": now})

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


def _delete_file_best_effort(storage, name: str) -> None:
    """ลบไฟล์ออกจาก storage แบบ best-effort เสมอ — ห้ามให้ error หลุดออกไป (ดู C2)
    เรียกใช้ทั้งจาก transaction.on_commit (นอก transaction แล้ว) และตอนกันไฟล์ค้างในเส้นทางล้มเหลว
    """
    if not name:
        return
    try:
        if storage.exists(name):
            storage.delete(name)
    except Exception:
        logger.exception("ลบไฟล์รูปห้อง %s ออกจาก storage ไม่สำเร็จ (ดำเนินการต่อโดยไม่แจ้ง error ให้ผู้ใช้)", name)


def save_room_photo(
    *,
    resource: Resource,
    image=None,
    caption: str = "",
    order: int = 0,
    is_cover: bool = False,
    photo: ResourcePhoto | None = None,
) -> ResourcePhoto:
    """สร้างหรือแก้ไข ResourcePhoto — จุดเดียวที่ทุกช่องทาง (admin/อื่น ๆ ในอนาคต) ต้องเรียกผ่าน (C2)

    ลำดับสำคัญกับการกันไฟล์กำพร้า (จงใจแยกขั้นเขียนไฟล์ออกจากขั้นบันทึกแถว DB อย่างชัดเจน
    เป็นสองขั้นตอน แทนที่จะปล่อยให้ ImageField.pre_save() ทำให้โดยปริยายตอน instance.save()
    — เพื่อให้เห็นขอบเขตชัดว่าไฟล์ถูกเขียนสำเร็จ ณ จุดไหน และทดสอบ/mock ได้ตรงจุด):
      1. เรียก full_clean() เสมอ ก่อนแตะ storage — ดักข้อผิดพลาดส่วนใหญ่ (ชนิด/ขนาดไฟล์, resource
         ไม่ใช่ห้อง, cover ซ้ำ) ได้ก่อนที่ไฟล์จะถูกเขียนจริง
      2. ถ้ามีไฟล์ใหม่ เขียนลง storage ทันที (ชื่อ UUID จาก upload_to) — ยังไม่ commit DB
      3. บันทึกแถว DB — ถ้าล้มเหลวหลังจากไฟล์ถูกเขียนแล้ว (ข้อ 2) เช่น DB ล่มกลางคัน ให้ลบไฟล์ใหม่
         ที่เพิ่งเขียนแบบ best-effort แล้ว re-raise exception เดิมกลับไปเสมอ (ห้ามกลืน error)
      4. กรณีแทนที่รูปเดิม (อัปโหลดไฟล์ใหม่ทับรูปที่มีอยู่แล้ว) ต้องอ่านชื่อไฟล์เดิมจากฐานข้อมูล
         ตรง ๆ (ไม่ใช่จาก instance ในหน่วยความจำ เพราะฟอร์ม/formset ของ admin อาจตั้งค่าฟิลด์ image
         ของ instance เป็นไฟล์ใหม่ไปแล้วก่อนเรียกฟังก์ชันนี้) แล้วลบไฟล์เก่าผ่าน transaction.on_commit
         เท่านั้น (กันไฟล์หายทั้งที่ transaction อาจ rollback)
    """
    if not settings.ROOM_PHOTO_UPLOAD_ENABLED:
        raise ValidationError(
            "ยังไม่ได้ตั้งค่าที่เก็บรูป (GS_BUCKET_NAME) — อัปโหลดได้เมื่อตั้งค่าตาม C5 แล้ว"
        )

    is_new = photo is None
    instance = photo if photo is not None else ResourcePhoto(resource=resource)
    if not is_new:
        instance.resource = resource

    old_image_name = None
    if not is_new and image is not None and instance.pk:
        old_image_name = ResourcePhoto.objects.filter(pk=instance.pk).values_list("image", flat=True).first()

    instance.caption = caption
    instance.order = order
    instance.is_cover = is_cover
    if image is not None:
        instance.image = image

    instance.full_clean()

    new_file_written = False
    try:
        if image is not None:
            # เขียนไฟล์ใหม่ลง storage ตอนนี้เลย (ยังไม่แตะ DB) — upload_to (room_photo_upload_to)
            # จะตั้งชื่อใหม่เป็น UUID ให้เองผ่าน generate_filename()
            instance.image.save(instance.image.name, instance.image.file, save=False)
            new_file_written = True
        with transaction.atomic():
            instance.save()
            if old_image_name and old_image_name != instance.image.name:
                storage = instance.image.storage
                transaction.on_commit(lambda: _delete_file_best_effort(storage, old_image_name))
    except Exception:
        # ไฟล์ใหม่ถูกเขียนลง storage สำเร็จแล้ว (ข้อ 2) ก่อนขั้นบันทึกแถว DB จะล้มเหลว — ลบทิ้งแบบ best-effort
        if new_file_written and instance.image and instance.image.name:
            _delete_file_best_effort(instance.image.storage, instance.image.name)
        raise
    return instance


def delete_room_photo(photo: ResourcePhoto) -> None:
    """ลบรูปห้อง — ลบแถว DB ก่อน แล้วลบไฟล์จริงใน storage ผ่าน transaction.on_commit เท่านั้น
    (กันกรณี transaction rollback แล้วไฟล์หายทั้งที่แถวยังอยู่จริง) callback ครอบ try/except + log เสมอ
    """
    storage = photo.image.storage
    name = photo.image.name
    with transaction.atomic():
        photo.delete()
        if name:
            transaction.on_commit(lambda: _delete_file_best_effort(storage, name))

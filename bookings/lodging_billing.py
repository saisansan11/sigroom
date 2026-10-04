"""Daily accommodation estimates; rates are selected by staff, never inferred from rank."""
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit.services import audit
from resources.models import Resource
from .lodging_models import CourseStudentLodging, LodgingMeterReading, LodgingRate
from .lodging_services import can_access_lodging_management, can_manage_cohort
from .models import Booking
from .services import can_view_details

ZERO = Decimal("0.00")


def stay_nights(check_in, check_out):
    if check_out < check_in:
        raise ValidationError("วันออกต้องไม่อยู่ก่อนวันเข้าพัก")
    return max(1, (check_out - check_in).days)


def accommodation_cost(rate, check_in, check_out, people=1):
    people = int(people)
    if people < 1:
        raise ValidationError("จำนวนผู้พักต้องไม่น้อยกว่า 1")
    if rate.effective_from > check_in:
        raise ValidationError("อัตรานี้ยังไม่มีผลในวันเข้าพัก")
    multiplier = people if rate.basis == LodgingRate.Basis.PERSON else 1
    return (rate.daily_price * stay_nights(check_in, check_out) * multiplier).quantize(Decimal("0.01"))


def electricity_cost(reading):
    if reading is None or reading.meter_out is None or reading.unit_price is None:
        return None
    if reading.meter_in < 0 or reading.meter_out < reading.meter_in or reading.unit_price < 0:
        raise ValidationError("เลขมิเตอร์หรือราคาค่าไฟไม่ถูกต้อง")
    return ((reading.meter_out - reading.meter_in) * reading.unit_price).quantize(Decimal("0.01"))


@transaction.atomic
def select_lodging_rate(*, actor, kind, source_id, rate_id, room=None):
    if not can_access_lodging_management(actor):
        raise PermissionDenied("คุณไม่มีสิทธิ์จัดการค่าใช้จ่ายที่พัก")
    rate = LodgingRate.objects.get(pk=rate_id)
    if kind == "student":
        source = CourseStudentLodging.objects.select_for_update().select_related("cohort", "room").get(pk=source_id)
        if not can_manage_cohort(actor, source.cohort):
            raise PermissionDenied("คุณไม่มีสิทธิ์จัดการผู้พักในหลักสูตรนี้")
        if room is not None and source.room_id != getattr(room, "pk", room):
            raise PermissionDenied("ผู้พักไม่ได้อยู่ในห้องนี้")
        check_in = source.cohort.check_in_date
    elif kind == "booking":
        source = Booking.objects.select_for_update().select_related("room").get(
            pk=source_id, room__room_category=Resource.Category.LODGING, public_lodging_access__isnull=False)
        if not can_view_details(actor, source):
            raise PermissionDenied("คุณไม่มีสิทธิ์จัดการคำขอที่พักนี้")
        if room is not None and source.room_id != getattr(room, "pk", room):
            raise PermissionDenied("ผู้พักไม่ได้อยู่ในห้องนี้")
        from django.utils import timezone
        check_in = timezone.localtime(source.start_at).date()
    else:
        raise ValidationError("ประเภทผู้พักไม่ถูกต้อง")
    if source.room.lodging_cooling != rate.cooling:
        raise ValidationError("อัตราต้องตรงกับประเภทแอร์หรือพัดลมของห้อง")
    if rate.effective_from > check_in:
        raise ValidationError("อัตรานี้ยังไม่มีผลในวันเข้าพัก")
    before = source.lodging_rate_id
    source.lodging_rate = rate
    source.save(update_fields=["lodging_rate"])
    audit(actor, source._meta.label_lower, source.pk, "lodging_rate_selected",
          before={"rate": before}, after={"rate": rate.pk})
    return source


@transaction.atomic
def save_meter(*, actor, room_id, check_in_date, check_out_date, meter_in, meter_out=None, unit_price=None):
    if not can_access_lodging_management(actor):
        raise PermissionDenied("คุณไม่มีสิทธิ์บันทึกมิเตอร์ไฟห้องพัก")
    room = Resource.objects.select_for_update().get(pk=room_id)
    reading = LodgingMeterReading.objects.select_for_update().filter(
        room=room, check_in_date=check_in_date, check_out_date=check_out_date).first()
    if reading is None:
        reading = LodgingMeterReading(room=room, check_in_date=check_in_date, check_out_date=check_out_date, recorded_by=actor)
    reading.meter_in, reading.meter_out, reading.unit_price = meter_in, meter_out, unit_price
    reading.save()
    return reading

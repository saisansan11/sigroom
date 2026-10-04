"""PR-7: Lodging Dashboard, Billing Estimates, Meter Readings, and Staff Access Gate."""
import csv
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
import uuid

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from audit.models import AuditLog
from bookings.admin import LodgingMeterReadingAdmin
from bookings.lodging_billing import (
    ZERO,
    accommodation_cost,
    electricity_cost,
    save_meter,
    select_lodging_rate,
    stay_nights,
)
from bookings.lodging_dashboard import room_occupancy
from bookings.lodging_models import (
    CourseLodgingCohort,
    CourseStudentLodging,
    LodgingMeterReading,
    LodgingRate,
    PublicLodgingAccess,
)
from bookings.models import Booking
from resources.models import Resource, ResourceApprover

pytestmark = pytest.mark.django_db


@pytest.fixture
def dashboard_env():
    unit = Unit.objects.create(code="SIG-TEST", name="หน่วยทดสอบที่พัก")
    staff_group, _ = Group.objects.get_or_create(name="lodging-staff")
    cohort_ct = ContentType.objects.get_for_model(CourseLodgingCohort)
    change_cohort_perm = Permission.objects.get(content_type=cohort_ct, codename="change_courselodgingcohort")
    add_cohort_perm = Permission.objects.get(content_type=cohort_ct, codename="add_courselodgingcohort")

    staff_user = User.objects.create_user(
        username="lodging_staff",
        email="lodging_staff@signalschool.ac.th",
        unit=unit,
        phone="0810000001",
    )
    staff_user.user_permissions.add(change_cohort_perm, add_cohort_perm)

    supervisor_a = User.objects.create_user(
        username="supervisor_a",
        email="sup_a@signalschool.ac.th",
        unit=unit,
        phone="0810000002",
    )
    supervisor_b = User.objects.create_user(
        username="supervisor_b",
        email="sup_b@signalschool.ac.th",
        unit=unit,
        phone="0810000003",
    )
    regular_user = User.objects.create_user(
        username="regular_user",
        email="user@signalschool.ac.th",
        unit=unit,
        phone="0810000004",
    )
    student_user = User.objects.create_user(
        username="student_user",
        email="student@signalschool.ac.th",
        unit=unit,
        phone="0810000005",
        is_lodging_student=True,
    )

    air_room_401 = Resource.objects.create(
        code="401",
        name="ห้องพัก 401 (แอร์)",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        lodging_cooling=Resource.Cooling.AIR,
        floor="4",
        capacity=4,
    )
    fan_room_417 = Resource.objects.create(
        code="417",
        name="ห้องพัก 417 (พัดลม)",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        lodging_cooling=Resource.Cooling.FAN,
        floor="4",
        capacity=4,
    )
    air_room_501 = Resource.objects.create(
        code="501",
        name="ห้องพัก 501 (แอร์)",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        lodging_cooling=Resource.Cooling.AIR,
        floor="5",
        capacity=2,
    )

    # Rates
    rate_air_person = LodgingRate.objects.create(
        category="นายสิบนักเรียน",
        cooling=Resource.Cooling.AIR,
        daily_price=Decimal("40.00"),
        monthly_price=Decimal("1000.00"),
        effective_from=date(2026, 1, 1),
        basis=LodgingRate.Basis.PERSON,
    )
    rate_air_officer = LodgingRate.objects.create(
        category="นายทหารนักเรียน",
        cooling=Resource.Cooling.AIR,
        daily_price=Decimal("50.00"),
        monthly_price=Decimal("1500.00"),
        effective_from=date(2026, 1, 1),
        basis=LodgingRate.Basis.PERSON,
    )
    rate_fan_person = LodgingRate.objects.create(
        category="นายสิบนักเรียน",
        cooling=Resource.Cooling.FAN,
        daily_price=Decimal("30.00"),
        monthly_price=Decimal("800.00"),
        effective_from=date(2026, 1, 1),
        basis=LodgingRate.Basis.PERSON,
    )
    rate_air_room = LodgingRate.objects.create(
        category="บุคคลภายนอกเหมาห้อง",
        cooling=Resource.Cooling.AIR,
        daily_price=Decimal("300.00"),
        monthly_price=Decimal("6000.00"),
        effective_from=date(2026, 1, 1),
        basis=LodgingRate.Basis.ROOM,
    )

    return {
        "unit": unit,
        "staff_user": staff_user,
        "supervisor_a": supervisor_a,
        "supervisor_b": supervisor_b,
        "regular_user": regular_user,
        "student_user": student_user,
        "air_room_401": air_room_401,
        "fan_room_417": fan_room_417,
        "air_room_501": air_room_501,
        "rate_air_person": rate_air_person,
        "rate_air_officer": rate_air_officer,
        "rate_fan_person": rate_fan_person,
        "rate_air_room": rate_air_room,
    }


# ==============================================================================
# 1. Decimal calculations & Minimum 1 night
# ==============================================================================

def test_stay_nights_calculation():
    check_in = date(2026, 10, 10)
    # Same day check-in and check-out is minimum 1 night
    assert stay_nights(check_in, check_in) == 1
    # 3-night stay
    assert stay_nights(check_in, date(2026, 10, 13)) == 3
    # Check-out before check-in raises ValidationError
    with pytest.raises(ValidationError, match="วันออกต้องไม่อยู่ก่อนวันเข้าพัก"):
        stay_nights(check_in, date(2026, 10, 9))


def test_accommodation_cost_decimal_quantization(dashboard_env):
    rate = dashboard_env["rate_air_person"]
    check_in = date(2026, 10, 10)
    check_out = date(2026, 10, 15)  # 5 nights

    cost = accommodation_cost(rate, check_in, check_out, people=2)
    assert isinstance(cost, Decimal)
    # 40.00 * 5 nights * 2 people = 400.00
    assert cost == Decimal("400.00")

    with pytest.raises(ValidationError, match="จำนวนผู้พักต้องไม่น้อยกว่า 1"):
        accommodation_cost(rate, check_in, check_out, people=0)

    # Future effective_from
    future_rate = LodgingRate.objects.create(
        category="อนาคต",
        cooling=Resource.Cooling.AIR,
        daily_price=Decimal("100.00"),
        monthly_price=Decimal("2000.00"),
        effective_from=date(2026, 12, 1),
        basis=LodgingRate.Basis.PERSON,
    )
    with pytest.raises(ValidationError, match="อัตรานี้ยังไม่มีผลในวันเข้าพัก"):
        accommodation_cost(future_rate, check_in, check_out, people=1)


def test_electricity_cost_decimal_quantization(dashboard_env):
    room = dashboard_env["air_room_401"]
    staff = dashboard_env["staff_user"]
    reading = LodgingMeterReading(
        room=room,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 15),
        meter_in=Decimal("100.250"),
        meter_out=Decimal("150.750"),
        unit_price=Decimal("4.5000"),
        recorded_by=staff,
    )
    # (150.750 - 100.250) * 4.5 = 50.5 * 4.5 = 227.25
    cost = electricity_cost(reading)
    assert isinstance(cost, Decimal)
    assert cost == Decimal("227.25")

    # Incomplete reading returns None
    assert electricity_cost(None) is None
    reading.meter_out = None
    assert electricity_cost(reading) is None

    # Invalid meter numbers raise
    reading.meter_out = Decimal("50.000")
    reading.unit_price = Decimal("4.5000")
    with pytest.raises(ValidationError, match="เลขมิเตอร์หรือราคาค่าไฟไม่ถูกต้อง"):
        electricity_cost(reading)


# ==============================================================================
# 2. Per-person vs Whole-room basis & Monthly comparison (>30 nights only)
# ==============================================================================

def test_basis_per_person_vs_whole_room(dashboard_env):
    person_rate = dashboard_env["rate_air_person"]
    room_rate = dashboard_env["rate_air_room"]
    check_in = date(2026, 10, 10)
    check_out = date(2026, 10, 12)  # 2 nights

    # Per person: 40.00 * 2 nights * 3 people = 240.00
    cost_person = accommodation_cost(person_rate, check_in, check_out, people=3)
    assert cost_person == Decimal("240.00")

    # Whole room: 300.00 * 2 nights * 1 = 600.00 (people multiplier ignored)
    cost_room = accommodation_cost(room_rate, check_in, check_out, people=3)
    assert cost_room == Decimal("600.00")


def test_monthly_comparison_never_auto_substitutes(dashboard_env):
    rate = dashboard_env["rate_air_person"]  # daily=40, monthly=1000
    room = dashboard_env["air_room_401"]
    sup = dashboard_env["supervisor_a"]

    # Case 1: 30 nights exactly -> monthly_comparison is None
    cohort_30 = CourseLodgingCohort.objects.create(
        title="รุ่น 30 คืน",
        slug="cohort-30",
        supervisor=sup,
        check_in_date=date(2026, 10, 1),
        check_out_date=date(2026, 10, 31),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort_30.rooms.add(room)
    s1 = CourseStudentLodging.objects.create(
        cohort=cohort_30,
        room=room,
        bed_number=1,
        rank="จ.ส.อ.",
        full_name="สมชาย มั่นคง",
        origin_unit="สส.",
        phone="0811111111",
        lodging_rate=rate,
    )

    rows = room_occupancy(date(2026, 10, 15))
    row = next(r for r in rows if r["room"].pk == room.pk)
    occ1 = row["occupants"][0]
    assert occ1["nights"] == 30
    assert occ1["monthly_comparison"] is None
    assert occ1["cost"] == Decimal("1200.00")  # 40 * 30

    # Case 2: 31 nights (>30) -> monthly_comparison is populated, but cost is STILL daily
    cohort_30.check_out_date = date(2026, 11, 1)  # 31 nights
    cohort_30.save()

    rows = room_occupancy(date(2026, 10, 15))
    row = next(r for r in rows if r["room"].pk == room.pk)
    occ2 = row["occupants"][0]
    assert occ2["nights"] == 31
    assert occ2["monthly_comparison"] == Decimal("1000.00")
    # Cost is NOT substituted: 40 * 31 = 1240.00, NOT 1000.00
    assert occ2["cost"] == Decimal("1240.00")
    assert row["accommodation"] == Decimal("1240.00")


# ==============================================================================
# 3. Rate selection, missing rates, and conflicting rates in dashboard
# ==============================================================================

def test_rate_selection_cooling_mismatch_and_effective_date(dashboard_env):
    staff = dashboard_env["staff_user"]
    sup = dashboard_env["supervisor_a"]
    air_room = dashboard_env["air_room_401"]
    fan_room = dashboard_env["fan_room_417"]

    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นทดสอบอัตรา",
        slug="rate-cohort",
        supervisor=sup,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 12),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort.rooms.add(air_room)

    student = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=air_room,
        bed_number=1,
        rank="ส.อ.",
        full_name="สายันต์ บุญมี",
        origin_unit="สส.",
        phone="0812345678",
    )

    # Fan rate on air room must fail
    with pytest.raises(ValidationError, match="อัตราต้องตรงกับประเภทแอร์หรือพัดลมของห้อง"):
        select_lodging_rate(
            actor=staff,
            kind="student",
            source_id=student.pk,
            rate_id=dashboard_env["rate_fan_person"].pk,
            room=air_room,
        )

    # Valid air rate succeeds and writes audit log
    select_lodging_rate(
        actor=staff,
        kind="student",
        source_id=student.pk,
        rate_id=dashboard_env["rate_air_person"].pk,
        room=air_room,
    )
    student.refresh_from_db()
    assert student.lodging_rate_id == dashboard_env["rate_air_person"].pk
    audit_entry = AuditLog.objects.filter(
        entity="bookings.coursestudentlodging",
        entity_id=str(student.pk),
        action="lodging_rate_selected",
    ).first()
    assert audit_entry is not None
    assert audit_entry.actor == staff


def test_dashboard_billing_conflict_on_room_basis(dashboard_env):
    room = dashboard_env["air_room_401"]
    sup = dashboard_env["supervisor_a"]

    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นชนอัตรา",
        slug="conflict-cohort",
        supervisor=sup,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 12),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort.rooms.add(room)

    # Student 1 has room rate
    CourseStudentLodging.objects.create(
        cohort=cohort, room=room, bed_number=1,
        rank="ส.อ.", full_name="คนที่ 1", origin_unit="สส.", phone="0810000011",
        lodging_rate=dashboard_env["rate_air_room"],
    )
    # Student 2 has different person rate in same room & stay
    CourseStudentLodging.objects.create(
        cohort=cohort, room=room, bed_number=2,
        rank="ร.ท.", full_name="คนที่ 2", origin_unit="สส.", phone="0810000012",
        lodging_rate=dashboard_env["rate_air_officer"],
    )

    rows = room_occupancy(date(2026, 10, 10))
    row = next(r for r in rows if r["room"].pk == room.pk)
    assert row["billing_conflict"] is True
    assert row["estimated"] is True
    assert row["missing_rates"] == 2
    assert row["accommodation"] == ZERO


# ==============================================================================
# 4. Meter readings for cooling rooms only, validation, and audit on save
# ==============================================================================

def test_meter_reading_cooling_rooms_only_and_validation(dashboard_env):
    air_room = dashboard_env["air_room_401"]
    fan_room = dashboard_env["fan_room_417"]
    staff = dashboard_env["staff_user"]
    sup = dashboard_env["supervisor_a"]

    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นมิเตอร์",
        slug="meter-cohort",
        supervisor=sup,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 15),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort.rooms.add(air_room, fan_room)

    # Fan room cannot have meter reading
    reading_fan = LodgingMeterReading(
        room=fan_room,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 15),
        meter_in=Decimal("10.000"),
        recorded_by=staff,
    )
    with pytest.raises(ValidationError) as exc:
        reading_fan.full_clean()
    assert "บันทึกมิเตอร์ได้เฉพาะห้องพักประเภทแอร์" in str(exc.value)

    # Negative meter_in
    reading_bad = LodgingMeterReading(
        room=air_room,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 15),
        meter_in=Decimal("-1.000"),
        recorded_by=staff,
    )
    with pytest.raises(ValidationError):
        reading_bad.full_clean()

    # meter_out < meter_in
    reading_bad2 = LodgingMeterReading(
        room=air_room,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 15),
        meter_in=Decimal("100.000"),
        meter_out=Decimal("90.000"),
        unit_price=Decimal("5.0000"),
        recorded_by=staff,
    )
    with pytest.raises(ValidationError) as exc2:
        reading_bad2.full_clean()
    assert "เลขมิเตอร์ออกต้องไม่น้อยกว่าเลขมิเตอร์เข้า" in str(exc2.value)

    # meter_out present but unit_price missing
    reading_bad3 = LodgingMeterReading(
        room=air_room,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 15),
        meter_in=Decimal("100.000"),
        meter_out=Decimal("150.000"),
        unit_price=None,
        recorded_by=staff,
    )
    with pytest.raises(ValidationError) as exc3:
        reading_bad3.full_clean()
    assert "กรุณากรอกราคาค่าไฟต่อหน่วยก่อนสรุปยอด" in str(exc3.value)


def test_meter_audit_on_every_save_and_admin_recorded_by_readonly(dashboard_env):
    air_room = dashboard_env["air_room_401"]
    staff = dashboard_env["staff_user"]
    sup = dashboard_env["supervisor_a"]

    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นมิเตอร์ออดิท",
        slug="meter-audit-cohort",
        supervisor=sup,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 15),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort.rooms.add(air_room)

    # Save via save_meter service
    reading = save_meter(
        actor=staff,
        room_id=air_room.pk,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 15),
        meter_in=Decimal("100.000"),
    )
    assert reading.recorded_by == staff
    audit_entry = AuditLog.objects.filter(
        entity="bookings.lodgingmeterreading",
        entity_id=str(reading.pk),
        action="lodging_meter_saved",
    ).first()
    assert audit_entry is not None
    assert audit_entry.actor == staff

    # Update via save_meter by supervisor_a: recorded_by is NOT altered
    save_meter(
        actor=sup,
        room_id=air_room.pk,
        check_in_date=date(2026, 10, 10),
        check_out_date=date(2026, 10, 15),
        meter_in=Decimal("100.000"),
        meter_out=Decimal("140.000"),
        unit_price=Decimal("4.0000"),
    )
    reading.refresh_from_db()
    assert reading.recorded_by == staff  # Kept original recorder
    assert reading.meter_out == Decimal("140.000")

    # Trying to mutate recorded_by directly raises ValidationError
    reading.recorded_by = sup
    with pytest.raises(ValidationError, match="ไม่อนุญาตให้แก้ไขผู้บันทึกเดิม"):
        reading.full_clean()

    # Admin save_model test
    admin_site = AdminSite()
    meter_admin = LodgingMeterReadingAdmin(LodgingMeterReading, admin_site)
    req = RequestFactory().post("/")
    req.user = sup
    reading.refresh_from_db()
    reading.unit_price = Decimal("4.2500")
    meter_admin.save_model(req, reading, form=None, change=True)
    reading.refresh_from_db()
    assert reading.recorded_by == staff  # Immutable in admin


# ==============================================================================
# 5. Occupancy combining CourseStudentLodging and approved Public Booking
#    without counting room holds twice
# ==============================================================================

def test_occupancy_combines_students_and_approved_public_bookings(dashboard_env):
    room_401 = dashboard_env["air_room_401"]  # capacity 4
    room_501 = dashboard_env["air_room_501"]  # capacity 2
    staff = dashboard_env["staff_user"]
    sup = dashboard_env["supervisor_a"]
    unit = dashboard_env["unit"]
    stay_date = date(2026, 10, 10)

    # Allocated cohort has 4 rooms hold (total 16 beds hold), but only 2 students assigned
    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นนักเรียน",
        slug="cohort-occupancy",
        supervisor=sup,
        check_in_date=stay_date,
        check_out_date=stay_date + timedelta(days=2),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort.rooms.add(room_401)
    CourseStudentLodging.objects.create(
        cohort=cohort, room=room_401, bed_number=1,
        rank="ส.อ.", full_name="นักเรียน 1", origin_unit="สส.", phone="0810000021",
    )
    CourseStudentLodging.objects.create(
        cohort=cohort, room=room_401, bed_number=2,
        rank="ส.อ.", full_name="นักเรียน 2", origin_unit="สส.", phone="0810000022",
    )

    # Approved Booking with PublicLodgingAccess for room 501
    zone = timezone.get_current_timezone()
    start_at = timezone.make_aware(datetime.combine(stay_date, time(14)), zone)
    end_at = timezone.make_aware(datetime.combine(stay_date + timedelta(days=2), time(12)), zone)
    booking_approved = Booking.objects.create(
        room=room_501,
        requester=staff,
        unit=unit,
        title="คำขอพักข้าราชการ",
        responsible_name="พ.ต. ประจักษ์",
        responsible_phone="0891234567",
        start_at=start_at,
        end_at=end_at,
        attendees=2,
        request_status=Booking.RequestStatus.APPROVED,
    )
    PublicLodgingAccess.objects.create(booking=booking_approved)

    # Pending Booking (should NOT be counted)
    booking_pending = Booking.objects.create(
        room=room_501,
        requester=staff,
        unit=unit,
        title="คำขอที่ยังไม่อนุมัติ",
        responsible_name="ผู้ขอรออนุมัติ",
        responsible_phone="0899999999",
        start_at=start_at,
        end_at=end_at,
        attendees=1,
        request_status=Booking.RequestStatus.PENDING,
    )
    PublicLodgingAccess.objects.create(booking=booking_pending)

    rows = room_occupancy(stay_date)
    r401 = next(r for r in rows if r["room"].pk == room_401.pk)
    r501 = next(r for r in rows if r["room"].pk == room_501.pk)

    # 401: exactly 2 occupants (NOT 4 capacity hold)
    assert r401["occupied"] == 2
    assert r401["free"] == 2
    assert r401["status"] == "occupied"

    # 501: exactly 2 attendees from approved booking (pending ignored)
    assert r501["occupied"] == 2
    assert r501["free"] == 0
    assert r501["status"] == "full"


# ==============================================================================
# 6. Checkout date boundary
# ==============================================================================

def test_checkout_date_boundary(dashboard_env):
    room = dashboard_env["air_room_401"]
    sup = dashboard_env["supervisor_a"]
    check_in = date(2026, 10, 10)
    check_out = date(2026, 10, 12)

    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นตรวจวันออก",
        slug="boundary-cohort",
        supervisor=sup,
        check_in_date=check_in,
        check_out_date=check_out,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort.rooms.add(room)
    CourseStudentLodging.objects.create(
        cohort=cohort, room=room, bed_number=1,
        rank="ส.อ.", full_name="สมเกียรติ", origin_unit="สส.", phone="0810000031",
    )

    # Check-in day (10th): 1 arrival, 0 departure, 1 occupant
    r_in = next(r for r in room_occupancy(check_in) if r["room"].pk == room.pk)
    assert r_in["arrivals"] == 1
    assert r_in["departures"] == 0
    assert r_in["occupied"] == 1

    # Middle day (11th): 0 arrival, 0 departure, 1 occupant
    r_mid = next(r for r in room_occupancy(date(2026, 10, 11)) if r["room"].pk == room.pk)
    assert r_mid["arrivals"] == 0
    assert r_mid["departures"] == 0
    assert r_mid["occupied"] == 1

    # Checkout day (12th): 0 arrival, 1 departure, 0 occupants for the night
    r_out = next(r for r in room_occupancy(check_out) if r["room"].pk == room.pk)
    assert r_out["arrivals"] == 0
    assert r_out["departures"] == 1
    assert r_out["occupied"] == 0
    assert r_out["status"] == "empty"


# ==============================================================================
# 7. Filters: status, day, floor
# ==============================================================================

def test_dashboard_filters_and_validation(client, dashboard_env):
    staff = dashboard_env["staff_user"]
    client.force_login(staff)

    # Invalid day date format
    resp_bad_date = client.get(reverse("bookings:lodging_dashboard"), {"day": "invalid-date"})
    assert resp_bad_date.status_code == 400
    assert "กรุณาเลือกวันที่ให้ถูกต้อง" in resp_bad_date.content.decode()

    # Out of range year (1999)
    resp_bad_year = client.get(reverse("bookings:lodging_dashboard"), {"day": "1999-12-31"})
    assert resp_bad_year.status_code == 400
    assert "เลือกวันที่ระหว่างปี 2543 ถึง 2742" in resp_bad_year.content.decode()

    # Floor filter = 4
    resp_f4 = client.get(reverse("bookings:lodging_dashboard"), {"floor": "4"})
    assert resp_f4.status_code == 200
    content_f4 = resp_f4.content.decode()
    assert "401" in content_f4
    assert "417" in content_f4
    assert "501" not in content_f4

    # Floor filter = 5
    resp_f5 = client.get(reverse("bookings:lodging_dashboard"), {"floor": "5"})
    assert resp_f5.status_code == 200
    content_f5 = resp_f5.content.decode()
    assert "501" in content_f5
    assert "401" not in content_f5

    # Status filter = full
    resp_full = client.get(reverse("bookings:lodging_dashboard"), {"status": "full"})
    assert resp_full.status_code == 200


# ==============================================================================
# 8. Constant / Query-bounded dashboard data
# ==============================================================================

def test_dashboard_queries_are_bounded_and_constant(dashboard_env):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    day = date(2026, 10, 10)
    # Baseline query count for room_occupancy
    with CaptureQueriesContext(connection) as ctx1:
        room_occupancy(day)
    count1 = len(ctx1)

    # Add 5 more lodging rooms
    for i in range(1, 6):
        Resource.objects.create(
            code=f"TEST-{i}",
            name=f"ห้องทดสอบ {i}",
            resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.LODGING,
            lodging_cooling=Resource.Cooling.AIR,
            floor="4",
            capacity=4,
        )

    # Query count must remain constant regardless of room count
    with CaptureQueriesContext(connection) as ctx2:
        room_occupancy(day)
    count2 = len(ctx2)

    assert count1 == count2


# ==============================================================================
# 9. Permissions & PII boundary across cohorts/bookings & malformed UUID
# ==============================================================================

def test_dashboard_permissions_negative(client, dashboard_env):
    url = reverse("bookings:lodging_dashboard")

    # Anonymous user is redirected to login
    client.logout()
    resp_anon = client.get(url)
    assert resp_anon.status_code == 302
    assert "/accounts/login/" in resp_anon.url

    # Student user is 403 Forbidden
    client.force_login(dashboard_env["student_user"])
    resp_student = client.get(url)
    assert resp_student.status_code == 403

    # Regular user is 403 Forbidden
    client.force_login(dashboard_env["regular_user"])
    resp_regular = client.get(url)
    assert resp_regular.status_code == 403

    # Lodging staff is 200 OK
    client.force_login(dashboard_env["staff_user"])
    resp_staff = client.get(url)
    assert resp_staff.status_code == 200


def test_supervisor_pii_boundary_across_cohorts(client, dashboard_env):
    room = dashboard_env["air_room_401"]
    sup_a = dashboard_env["supervisor_a"]
    sup_b = dashboard_env["supervisor_b"]
    stay_date = date(2026, 10, 10)

    cohort_b = CourseLodgingCohort.objects.create(
        title="รุ่นหลักสูตร B",
        slug="cohort-b",
        supervisor=sup_b,
        check_in_date=stay_date,
        check_out_date=stay_date + timedelta(days=2),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort_b.rooms.add(room)

    # Student in cohort B (has sensitive PII: name, phone, etc.)
    student_b = CourseStudentLodging.objects.create(
        cohort=cohort_b,
        room=room,
        bed_number=1,
        rank="จ.ส.ต.",
        full_name="ความลับ ทางราชการ",
        origin_unit="ศสส.",
        phone="0899999999",
        note="ข้อมูลส่วนตัว",
    )

    # Supervisor A has cohort A, but NOT cohort B
    CourseLodgingCohort.objects.create(
        title="รุ่นหลักสูตร A",
        slug="cohort-a",
        supervisor=sup_a,
        check_in_date=stay_date,
        check_out_date=stay_date + timedelta(days=2),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )

    client.force_login(sup_a)
    room_url = reverse("bookings:lodging_dashboard_room", args=[room.pk])
    resp = client.get(room_url, {"day": stay_date.isoformat()})
    assert resp.status_code == 200
    html = resp.content.decode()

    # Supervisor A MUST NOT see the student's name, phone, or unit!
    assert "ความลับ ทางราชการ" not in html
    assert "0899999999" not in html
    assert "ข้อมูลส่วนตัว" not in html
    assert "ผู้พักที่อยู่ในความดูแลของเจ้าหน้าที่อื่น" in html
    # Supervisor A cannot see rate change form for cohort B student
    assert f'value="{student_b.pk}"' not in html

    # Attempting to POST rate change for student_b by Supervisor A must be 403 Forbidden
    post_resp = client.post(room_url, {
        "action": "rate",
        "kind": "student",
        "source_id": student_b.pk,
        "rate_id": dashboard_env["rate_air_person"].pk,
    })
    assert post_resp.status_code == 403


def test_malformed_and_wrong_uuid_handling(client, dashboard_env):
    staff = dashboard_env["staff_user"]
    room = dashboard_env["air_room_401"]
    client.force_login(staff)
    room_url = reverse("bookings:lodging_dashboard_room", args=[room.pk])

    # Malformed UUID in booking source_id
    resp_malformed = client.post(room_url, {
        "action": "rate",
        "kind": "booking",
        "source_id": "not-a-valid-uuid",
        "rate_id": dashboard_env["rate_air_person"].pk,
    })
    assert resp_malformed.status_code == 200  # Returns page with flash error message, does not crash 500
    assert "not-a-valid-uuid" in resp_malformed.content.decode()

    # Non-existent UUID
    random_uuid = str(uuid.uuid4())
    resp_nonexistent = client.post(room_url, {
        "action": "rate",
        "kind": "booking",
        "source_id": random_uuid,
        "rate_id": dashboard_env["rate_air_person"].pk,
    })
    assert resp_nonexistent.status_code == 200
    assert "กรุณาเลือกอัตราที่ถูกต้อง" in resp_nonexistent.content.decode()

    # Invalid kind
    resp_invalid_kind = client.post(room_url, {
        "action": "rate",
        "kind": "invalid_kind",
        "source_id": "1",
        "rate_id": dashboard_env["rate_air_person"].pk,
    })
    assert resp_invalid_kind.status_code == 400


# ==============================================================================
# 10. CSRF Protection on write actions
# ==============================================================================

def test_csrf_protection_on_rate_and_meter(dashboard_env):
    csrf_client = Client(enforce_csrf_checks=True)
    staff = dashboard_env["staff_user"]
    room = dashboard_env["air_room_401"]
    csrf_client.force_login(staff)

    room_url = reverse("bookings:lodging_dashboard_room", args=[room.pk])

    # POST without CSRF token must fail with 403
    resp_rate = csrf_client.post(room_url, {"action": "rate"})
    assert resp_rate.status_code == 403

    resp_meter = csrf_client.post(room_url, {"action": "meter"})
    assert resp_meter.status_code == 403


# ==============================================================================
# 11. CSV room-total export with formula injection escaping and no PII
# ==============================================================================

def test_csv_room_totals_export_and_formula_escaping(client, dashboard_env):
    staff = dashboard_env["staff_user"]
    sup = dashboard_env["supervisor_a"]
    stay_date = date(2026, 10, 10)

    # Create room with formula characters in code
    formula_room = Resource.objects.create(
        code="=SUM(1+1)",
        name="ห้องทดสอบสูตร",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        lodging_cooling=Resource.Cooling.AIR,
        floor="4",
        capacity=2,
    )
    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นทดสอบ CSV",
        slug="csv-cohort",
        supervisor=sup,
        check_in_date=stay_date,
        check_out_date=stay_date + timedelta(days=2),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort.rooms.add(formula_room)
    CourseStudentLodging.objects.create(
        cohort=cohort, room=formula_room, bed_number=1,
        rank="พ.อ.", full_name="พลเอก ลับสุดยอด", origin_unit="ศสส.", phone="0899999999",
        lodging_rate=dashboard_env["rate_air_officer"],
    )

    client.force_login(staff)
    export_url = reverse("bookings:lodging_dashboard_export") + f"?day={stay_date.isoformat()}"
    resp = client.get(export_url)
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/csv")
    assert resp["Content-Disposition"] == 'attachment; filename="lodging-room-totals.csv"'

    content = resp.content.decode("utf-8")
    # Must start with UTF-8 BOM
    assert content.startswith("\ufeff")

    # MUST NOT contain student name or phone (No PII)
    assert "ลับสุดยอด" not in content
    assert "0899999999" not in content

    # Formula injection must be escaped with leading single quote '
    assert "'=SUM(1+1)" in content

    # Audit log was written
    audit_log = AuditLog.objects.filter(
        entity="bookings.lodging_dashboard",
        action="lodging_totals_csv_exported",
    ).first()
    assert audit_log is not None


# ==============================================================================
# 12. HTMX partial/drawer behavior
# ==============================================================================

def test_htmx_partial_drawer_responses(client, dashboard_env):
    staff = dashboard_env["staff_user"]
    room = dashboard_env["air_room_401"]
    client.force_login(staff)

    # 1. Grid polling partial
    grid_url = reverse("bookings:lodging_dashboard")
    resp_grid_partial = client.get(grid_url, HTTP_HX_TARGET="lodging-dashboard-grid")
    assert resp_grid_partial.status_code == 200
    html_grid = resp_grid_partial.content.decode().lower()
    assert "dashboard-summary" in html_grid
    assert "<!doctype html>" not in html_grid  # Partial, no full page wrapper

    # Full dashboard page
    resp_grid_full = client.get(grid_url)
    assert resp_grid_full.status_code == 200
    assert "<!doctype html>" in resp_grid_full.content.decode().lower()

    # 2. Room drawer partial
    room_url = reverse("bookings:lodging_dashboard_room", args=[room.pk])
    resp_room_partial = client.get(room_url, HTTP_HX_TARGET="lodging-room-panel")
    assert resp_room_partial.status_code == 200
    html_room = resp_room_partial.content.decode().lower()
    assert "dashboard-room-detail" in html_room
    assert "<!doctype html>" not in html_room

    # Full room page
    resp_room_full = client.get(room_url)
    assert resp_room_full.status_code == 200
    assert "<!doctype html>" in resp_room_full.content.decode().lower()


# ==============================================================================
# 13. Navigation keeps links to legacy workspace/manage
# ==============================================================================

def test_dashboard_navigation_preserves_legacy_links(client, dashboard_env):
    staff = dashboard_env["staff_user"]
    client.force_login(staff)

    resp = client.get(reverse("bookings:lodging_dashboard"))
    assert resp.status_code == 200
    html = resp.content.decode()

    # Contains links to legacy workspace and manage
    assert reverse("bookings:lodging_workspace") in html
    assert reverse("bookings:lodging_manage") in html
    assert reverse("bookings:lodging_dashboard_export") in html


# ==============================================================================
# 14. Historical meter access after released cohorts
# ==============================================================================

def test_historical_meter_access_after_released_cohort(client, dashboard_env):
    room = dashboard_env["air_room_401"]
    staff = dashboard_env["staff_user"]
    sup = dashboard_env["supervisor_a"]
    check_in = date(2026, 9, 1)
    check_out = date(2026, 9, 10)

    # Cohort that was previously active and is now RELEASED
    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นจบแล้ว",
        slug="released-cohort",
        supervisor=sup,
        check_in_date=check_in,
        check_out_date=check_out,
        allocation_status=CourseLodgingCohort.AllocationStatus.RELEASED,
    )
    cohort.rooms.add(room)

    # Staff records initial check-in meter reading
    reading = LodgingMeterReading.objects.create(
        room=room,
        check_in_date=check_in,
        check_out_date=check_out,
        meter_in=Decimal("500.000"),
        recorded_by=staff,
    )

    # After cohort is released, staff enters final checkout meter_out and unit_price
    reading.meter_out = Decimal("580.000")
    reading.unit_price = Decimal("4.5000")
    reading.save()  # full_clean() must succeed!
    reading.refresh_from_db()
    assert reading.meter_out == Decimal("580.000")

    # Staff views room panel on a date within that historical stay
    client.force_login(staff)
    room_url = reverse("bookings:lodging_dashboard_room", args=[room.pk])
    resp = client.get(room_url, {"day": "2026-09-05"})
    assert resp.status_code == 200
    html = resp.content.decode()
    # Meter form is pre-filled with the historical reading
    assert 'value="500.000"' in html
    assert 'value="580.000"' in html
    assert 'value="2026-09-01"' in html
    assert 'value="2026-09-10"' in html
    assert 'value="01/09/2026"' not in html
    assert 'value="10/09/2026"' not in html


# ==============================================================================
# 15. HTML5 ISO date rendering and MeterForm POST flow
# ==============================================================================

def test_air_room_panel_meter_form_renders_iso_dates_and_posts_valid_reading(client, dashboard_env):
    room = dashboard_env["air_room_401"]
    staff = dashboard_env["staff_user"]
    sup = dashboard_env["supervisor_a"]
    check_in = date(2026, 10, 4)
    check_out = date(2026, 10, 7)

    cohort = CourseLodgingCohort.objects.create(
        title="รุ่นทดสอบมิเตอร์ ISO",
        slug="iso-meter-cohort",
        supervisor=sup,
        check_in_date=check_in,
        check_out_date=check_out,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    )
    cohort.rooms.add(room)

    client.force_login(staff)
    room_url = reverse("bookings:lodging_dashboard_room", args=[room.pk])

    # 1. GET room panel on check-in day: initial values rendered as YYYY-MM-DD
    resp_get = client.get(room_url, {"day": "2026-10-04"})
    assert resp_get.status_code == 200
    html_get = resp_get.content.decode()

    # Browser QA fix verification: HTML date inputs require YYYY-MM-DD
    assert 'name="check_in_date" value="2026-10-04"' in html_get
    assert 'name="check_out_date" value="2026-10-07"' in html_get
    assert 'value="04/10/2026"' not in html_get
    assert 'value="07/10/2026"' not in html_get

    # 2. POST valid meter reading using ISO dates
    post_data = {
        "action": "meter",
        "check_in_date": "2026-10-04",
        "check_out_date": "2026-10-07",
        "meter_in": "100.500",
        "meter_out": "145.250",
        "unit_price": "5.0000",
    }
    resp_post = client.post(f"{room_url}?day=2026-10-04", post_data)
    assert resp_post.status_code == 200
    html_post = resp_post.content.decode()
    assert "บันทึกมิเตอร์แล้ว ค่าไฟคิดรวมทั้งห้อง" in html_post

    reading = LodgingMeterReading.objects.get(room=room, check_in_date=check_in, check_out_date=check_out)
    assert reading.meter_in == Decimal("100.500")
    assert reading.meter_out == Decimal("145.250")
    assert reading.unit_price == Decimal("5.0000")

    # Re-rendered panel preserves ISO values
    assert 'name="check_in_date" value="2026-10-04"' in html_post
    assert 'name="check_out_date" value="2026-10-07"' in html_post
    assert 'value="100.500"' in html_post
    assert 'value="145.250"' in html_post

    # 3. POST invalid meter reading (bound error case) re-renders bound ISO values
    post_invalid = {
        "action": "meter",
        "check_in_date": "2026-10-04",
        "check_out_date": "2026-10-07",
        "meter_in": "200.000",
        "meter_out": "100.000",  # invalid: meter_out < meter_in
        "unit_price": "5.0000",
    }
    resp_invalid = client.post(f"{room_url}?day=2026-10-04", post_invalid)
    assert resp_invalid.status_code == 200
    html_invalid = resp_invalid.content.decode()
    assert "เลขมิเตอร์ออกต้องไม่น้อยกว่าเลขมิเตอร์เข้า" in html_invalid
    assert 'name="check_in_date" value="2026-10-04"' in html_invalid
    assert 'name="check_out_date" value="2026-10-07"' in html_invalid


def test_meter_form_direct_widget_format_and_parsing():
    from bookings.lodging_dashboard_views import MeterForm

    # Initial dict with date objects renders YYYY-MM-DD
    form_initial = MeterForm(initial={
        "check_in_date": date(2026, 10, 4),
        "check_out_date": date(2026, 10, 7),
    })
    as_p_initial = form_initial.as_p()
    assert 'name="check_in_date" value="2026-10-04"' in as_p_initial
    assert 'name="check_out_date" value="2026-10-07"' in as_p_initial
    assert "04/10/2026" not in as_p_initial
    assert "07/10/2026" not in as_p_initial

    # Bound with ISO strings parses into date objects
    form_bound = MeterForm(data={
        "check_in_date": "2026-10-04",
        "check_out_date": "2026-10-07",
        "meter_in": "100.000",
    })
    assert form_bound.is_valid()
    assert form_bound.cleaned_data["check_in_date"] == date(2026, 10, 4)
    assert form_bound.cleaned_data["check_out_date"] == date(2026, 10, 7)

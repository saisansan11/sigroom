from datetime import date, datetime, time, timedelta
from io import StringIO

import pytest
from django.core import management
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from bookings.lodging_services import (
    cohort_hold_range,
    generate_cohort_qr_svg,
    generate_line_share_url,
    get_canonical_public_url,
    normalize_phone,
    update_cohort_allocation,
)
from bookings.models import Booking
from bookings.services import BookingConflict, place_holds, validate_booking_window
from resources.models import Resource, ResourceRule


pytestmark = pytest.mark.django_db


@pytest.fixture
def lodging_data():
    unit = Unit.objects.create(code="EDU", name="กองการศึกษา")
    user = User.objects.create_user(
        username="lodging-supervisor",
        email="lodging-supervisor@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    other = User.objects.create_user(
        username="other-supervisor",
        email="other-supervisor@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    superuser = User.objects.create_superuser(
        username="lodging-admin",
        email="lodging-admin@signalschool.ac.th",
        password="Password-2569",
    )
    rooms = []
    for code in ("DORM-A", "DORM-B", "DORM-C"):
        room = Resource.objects.create(
            code=code,
            name=f"ห้องพัก {code}",
            resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.LODGING,
            capacity=4,
        )
        ResourceRule.objects.create(resource=room)
        rooms.append(room)
    return {"unit": unit, "user": user, "other": other, "superuser": superuser, "rooms": rooms}


def _dates(offset=7, days=3):
    start = timezone.localdate() + timedelta(days=offset)
    return start, start + timedelta(days=days)


def make_cohort(data, slug="cohort-a", rooms=None, *, status="allocated", active=True, start=None, end=None, actor=None):
    start, end = (start, end) if start and end else _dates()
    cohort = CourseLodgingCohort(
        title=slug,
        slug=slug,
        supervisor=data["user"],
        unit=data["unit"],
    )
    return update_cohort_allocation(
        cohort=cohort,
        rooms=rooms if rooms is not None else [data["rooms"][0]],
        check_in_date=start,
        check_out_date=end,
        allocation_status=status,
        is_active=active,
        beds_per_room=4,
        actor=actor if actor is not None else data["user"],
    )


def test_phone_normalization_and_empty_rejection(lodging_data):
    assert normalize_phone("081-111 2222") == "0811112222"
    cohort = make_cohort(lodging_data, status="released", active=False, rooms=[])
    room = lodging_data["rooms"][0]
    student = CourseStudentLodging(
        cohort=cohort,
        room=room,
        rank="ร.อ.",
        full_name="สมชาย ใจดี",
        origin_unit="ศสส.",
        phone="081-111-2222",
    )
    with pytest.raises(ValidationError):
        student.save()
    cohort.rooms.add(room)
    student.save()
    assert student.phone == "0811112222"
    duplicate = CourseStudentLodging(
        cohort=cohort,
        room=room,
        bed_number=2,
        rank="ร.อ.",
        full_name="คนที่สอง",
        origin_unit="ศสส.",
        phone="081 111 2222",
    )
    with pytest.raises(ValidationError):
        duplicate.save()


def test_cohort_overlap_and_regular_hold_conflict(lodging_data):
    start, end = _dates()
    room = lodging_data["rooms"][0]
    make_cohort(lodging_data, "cohort-a", [room], start=start, end=end)
    with pytest.raises(ValidationError, match="ชนกับรอบหลักสูตร"):
        make_cohort(lodging_data, "cohort-b", [room], start=start, end=end)

    regular_start = timezone.make_aware(datetime.combine(start, time(9)))
    regular_end = regular_start + timedelta(hours=1)
    booking = Booking.objects.create(
        room=lodging_data["rooms"][1],
        requester=lodging_data["user"],
        unit=lodging_data["unit"],
        title="งานปกติ",
        start_at=regular_start,
        end_at=regular_end,
        request_status=Booking.RequestStatus.APPROVED,
    )
    place_holds(booking)
    with pytest.raises(ValidationError, match="การจองห้องปกติ"):
        make_cohort(lodging_data, "cohort-c", [lodging_data["rooms"][1]], start=start, end=end)


def test_regular_booking_respects_allocated_cohort(lodging_data):
    start, end = _dates()
    room = lodging_data["rooms"][0]
    make_cohort(lodging_data, rooms=[room], start=start, end=end)
    booking_start = timezone.make_aware(datetime.combine(start, time(9)))
    booking = Booking(
        room=room,
        requester=lodging_data["user"],
        unit=lodging_data["unit"],
        title="งานปกติ",
        start_at=booking_start,
        end_at=booking_start + timedelta(hours=1),
    )
    errors = validate_booking_window(room, booking.start_at, booking.end_at, lodging_data["user"])
    assert any("ถูกสงวนไว้" in error for error in errors)
    with pytest.raises(BookingConflict):
        place_holds(booking)


def test_state_machine_and_allocation_invariants(lodging_data):
    cohort = CourseLodgingCohort(
        title="invalid",
        slug="invalid",
        supervisor=lodging_data["user"],
        unit=lodging_data["unit"],
        check_in_date=date.today(),
        check_out_date=date.today(),
        allocation_status=CourseLodgingCohort.AllocationStatus.RELEASED,
        is_active=True,
    )
    with pytest.raises(ValidationError):
        cohort.full_clean()
    with pytest.raises(ValidationError, match="ต้องมีห้อง"):
        make_cohort(lodging_data, "no-room", rooms=[], status="allocated", active=False)


def test_student_room_and_bed_invariants(lodging_data):
    cohort = make_cohort(lodging_data, rooms=[lodging_data["rooms"][0]])
    outside = CourseStudentLodging(
        cohort=cohort,
        room=lodging_data["rooms"][1],
        rank="ร.อ.",
        full_name="ห้องนอก",
        origin_unit="ศสส.",
        phone="0800000001",
    )
    with pytest.raises(ValidationError, match="ไม่ได้อยู่"):
        outside.save()
    too_high = CourseStudentLodging(
        cohort=cohort,
        room=lodging_data["rooms"][0],
        bed_number=5,
        rank="ร.อ.",
        full_name="เตียงเกิน",
        origin_unit="ศสส.",
        phone="0800000002",
    )
    with pytest.raises(ValidationError, match="ระหว่าง"):
        too_high.save()
    zero_bed = CourseStudentLodging(
        cohort=cohort,
        room=lodging_data["rooms"][0],
        bed_number=0,
        rank="ร.อ.",
        full_name="เตียงศูนย์",
        origin_unit="ศสส.",
        phone="0800000003",
    )
    with pytest.raises(ValidationError, match="ระหว่าง"):
        zero_bed.save()


def test_unit_update_rolls_back_with_failed_allocation_in_same_atomic_block(lodging_data):
    # จำลองรูปแบบเดียวกับ seed_pilot: อัปเดต unit แล้วเรียก update_cohort_allocation
    # ในบล็อก transaction.atomic() เดียวกัน — ถ้า allocation ล้มเหลว unit ต้องย้อนกลับด้วย
    from django.db import transaction

    other_unit = Unit.objects.create(code="OTHER-UNIT", name="หน่วยอื่นสำหรับทดสอบ")
    start, end = _dates()
    cohort = make_cohort(lodging_data, "rollback-target", rooms=[lodging_data["rooms"][0]], start=start, end=end)
    original_unit_id = cohort.unit_id
    make_cohort(lodging_data, "rollback-blocker", rooms=[lodging_data["rooms"][1]], start=start, end=end)

    with pytest.raises(ValidationError, match="ชนกับรอบหลักสูตร"):
        with transaction.atomic():
            cohort.unit = other_unit
            cohort.save(update_fields=["unit"])
            update_cohort_allocation(
                cohort=cohort,
                rooms=[lodging_data["rooms"][1]],
                check_in_date=start,
                check_out_date=end,
                allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
                is_active=True,
                beds_per_room=4,
                actor=lodging_data["user"],
            )

    cohort.refresh_from_db()
    assert cohort.unit_id == original_unit_id


def test_cannot_remove_booked_room_or_reduce_beds(lodging_data):
    start, end = _dates()
    cohort = make_cohort(lodging_data, rooms=lodging_data["rooms"][:2], start=start, end=end)
    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=lodging_data["rooms"][0],
        bed_number=2,
        rank="ร.อ.",
        full_name="มีผู้พัก",
        origin_unit="ศสส.",
        phone="0800000010",
    )
    with pytest.raises(ValidationError, match="ถอดห้อง"):
        update_cohort_allocation(
            cohort=cohort,
            rooms=[lodging_data["rooms"][1]],
            check_in_date=start,
            check_out_date=end,
            allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
            is_active=True,
            beds_per_room=4,
            actor=lodging_data["user"],
        )
    with pytest.raises(ValidationError, match="ลดจำนวนเตียง"):
        update_cohort_allocation(
            cohort=cohort,
            rooms=lodging_data["rooms"][:2],
            check_in_date=start,
            check_out_date=end,
            allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
            is_active=True,
            beds_per_room=1,
            actor=lodging_data["user"],
        )


def test_early_release_and_date_bypass_are_blocked(lodging_data):
    start, end = _dates()
    cohort = make_cohort(lodging_data, start=start, end=end)
    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=lodging_data["rooms"][0],
        rank="ร.อ.",
        full_name="ผู้พักปัจจุบัน",
        origin_unit="ศสส.",
        phone="0800000020",
    )
    common = dict(
        cohort=cohort,
        rooms=[lodging_data["rooms"][0]],
        check_in_date=start,
        check_out_date=end,
        beds_per_room=4,
        actor=lodging_data["user"],
    )
    with pytest.raises(ValidationError, match="ไม่สามารถปลด"):
        update_cohort_allocation(
            **common,
            allocation_status=CourseLodgingCohort.AllocationStatus.RELEASED,
            is_active=False,
        )
    with pytest.raises(ValidationError, match="ไม่สามารถปลด"):
        bypass_values = {**common, "check_out_date": timezone.localdate() - timedelta(days=1)}
        update_cohort_allocation(
            **bypass_values,
            allocation_status=CourseLodgingCohort.AllocationStatus.RELEASED,
            is_active=False,
        )


def test_force_release_requires_superuser_and_reason(lodging_data):
    start, end = _dates()
    cohort = make_cohort(lodging_data, start=start, end=end)
    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=lodging_data["rooms"][0],
        rank="ร.อ.",
        full_name="ผู้พัก",
        origin_unit="ศสส.",
        phone="0800000030",
    )
    common = dict(
        cohort=cohort,
        rooms=[lodging_data["rooms"][0]],
        check_in_date=start,
        check_out_date=end,
        allocation_status=CourseLodgingCohort.AllocationStatus.RELEASED,
        is_active=False,
        beds_per_room=4,
        force_release=True,
        release_reason="ย้ายอาคารตามคำสั่ง",
    )
    with pytest.raises(PermissionDenied):
        update_cohort_allocation(**common, actor=lodging_data["user"])
    released = update_cohort_allocation(**common, actor=lodging_data["superuser"])
    assert released.allocation_status == CourseLodgingCohort.AllocationStatus.RELEASED


def test_public_privacy_duplicate_phone_and_pass_headers(client, lodging_data):
    cohort = make_cohort(lodging_data)
    student = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=lodging_data["rooms"][0],
        rank="ร.อ.",
        full_name="สมชาย ใจดี",
        origin_unit="หน่วยลับ",
        phone="081-111-2222",
        note="ข้อมูลสุขภาพส่วนตัว",
    )
    portal = client.get(reverse("bookings:lodging_portal", args=[cohort.slug]))
    content = portal.content.decode()
    assert "สมชาย ใจดี" not in content
    assert "หน่วยลับ" not in content
    assert "0811112222" not in content
    duplicate = client.post(
        reverse("bookings:lodging_book_bed", args=[cohort.slug]),
        {"room_id": lodging_data["rooms"][0].pk, "bed_number": 2, "rank": "ร.ท.", "full_name": "คนซ้ำ", "origin_unit": "ศสส.", "phone": "081 111 2222"},
        follow=False,
    )
    assert duplicate.status_code == 302
    assert "pass" not in duplicate["Location"]
    assert lodging_data["rooms"][0].code not in duplicate.get("X-Message", "")
    pass_response = client.get(reverse("bookings:lodging_pass", args=[cohort.slug, student.pk]))
    pass_content = pass_response.content.decode()
    assert "ข้อมูลสุขภาพส่วนตัว" not in pass_content
    assert "0811112222" not in pass_content
    assert pass_response["Cache-Control"] == "no-store"
    assert pass_response["X-Content-Type-Options"] == "nosniff"


def test_share_qr_and_canonical_url(settings, rf, lodging_data):
    settings.PUBLIC_BASE_URL = "https://sigroom.example.test/"
    request = rf.get("/lodging/")
    assert get_canonical_public_url(request, "/lodging/c/demo/") == "https://sigroom.example.test/lodging/c/demo/"
    share = generate_line_share_url("รุ่น 70", "https://sigroom.example.test/lodging/c/demo/")
    assert share.startswith("https://line.me/R/share?text=")
    svg = generate_cohort_qr_svg("https://sigroom.example.test/lodging/c/demo/")
    assert svg.startswith(b"<?xml") or b"<svg" in svg
    hold = cohort_hold_range(date(2026, 9, 4), date(2026, 9, 5))
    assert hold.lower.date() == date(2026, 9, 4)
    assert hold.upper.date() == date(2026, 9, 6)


def test_lodging_index_and_supervisor_isolation(client, lodging_data):
    cohort = make_cohort(lodging_data, "owned")
    other_cohort = CourseLodgingCohort(
        title="other",
        slug="other",
        supervisor=lodging_data["other"],
        unit=lodging_data["unit"],
        check_in_date=timezone.localdate(),
        check_out_date=timezone.localdate() + timedelta(days=1),
        allocation_status=CourseLodgingCohort.AllocationStatus.RELEASED,
        is_active=False,
    )
    other_cohort.save()
    public = client.get(reverse("bookings:lodging_index"))
    assert cohort.title in public.content.decode()
    client.force_login(lodging_data["user"])
    assert client.get(reverse("bookings:lodging_cohort_detail", args=[cohort.slug])).status_code == 200
    assert client.get(reverse("bookings:lodging_cohort_detail", args=[other_cohort.slug])).status_code == 403


def test_calendar_and_today_board_show_lodging_reservation(client, lodging_data):
    today = timezone.localdate()
    cohort = make_cohort(
        lodging_data,
        "today-reservation",
        rooms=[lodging_data["rooms"][0]],
        start=today,
        end=today + timedelta(days=2),
    )
    calendar = client.get(reverse("bookings:calendar"))
    assert calendar.status_code == 200
    assert calendar.context["stat_free_now"] == 2
    assert "สงวนที่พักหลักสูตร" in calendar.content.decode()
    events = client.get(
        reverse("bookings:calendar_events"),
        {"start": today.isoformat(), "end": (today + timedelta(days=3)).isoformat(), "category": "lodging"},
    ).json()
    reservation_events = [item for item in events if item.get("extendedProps", {}).get("status") == "lodging_reserved"]
    assert reservation_events
    assert reservation_events[0]["extendedProps"]["room"] == lodging_data["rooms"][0].code
    assert reservation_events[0]["url"] == reverse("bookings:lodging_portal", args=[cohort.slug])


def test_calendar_events_room_filter_excludes_other_rooms_in_cohort(client, lodging_data):
    today = timezone.localdate()
    make_cohort(
        lodging_data,
        "multi-room-cohort",
        rooms=lodging_data["rooms"][:2],
        start=today,
        end=today + timedelta(days=2),
    )
    events = client.get(
        reverse("bookings:calendar_events"),
        {"start": today.isoformat(), "end": (today + timedelta(days=3)).isoformat(), "room": lodging_data["rooms"][0].code},
    ).json()
    reservation_events = [item for item in events if item.get("extendedProps", {}).get("status") == "lodging_reserved"]
    assert reservation_events
    assert {item["extendedProps"]["room"] for item in reservation_events} == {lodging_data["rooms"][0].code}


def test_admin_save_failure_does_not_crash_or_persist(admin_client, lodging_data):
    start, end = _dates()
    make_cohort(lodging_data, "already-allocated", rooms=[lodging_data["rooms"][0]], start=start, end=end)
    other = make_cohort(lodging_data, "editable-cohort", rooms=[lodging_data["rooms"][1]], start=start, end=end)

    url = reverse("admin:bookings_courselodgingcohort_change", args=[other.pk])
    response = admin_client.post(
        url,
        {
            "title": other.title,
            "slug": other.slug,
            "supervisor": other.supervisor_id,
            "check_in_date": start.isoformat(),
            "check_out_date": end.isoformat(),
            "beds_per_room": 4,
            "allocation_status": CourseLodgingCohort.AllocationStatus.ALLOCATED,
            "is_active": "on",
            # ห้องชนกับ "already-allocated" — กติกานี้ตรวจใน update_cohort_allocation
            # เท่านั้น ไม่มีการตรวจซ้ำระดับฟอร์ม admin จึงต้องพังที่ service เสมอ
            "rooms": [str(lodging_data["rooms"][0].pk)],
            "students-TOTAL_FORMS": "0",
            "students-INITIAL_FORMS": "0",
            "students-MIN_NUM_FORMS": "0",
            "students-MAX_NUM_FORMS": "1000",
        },
    )
    assert response.status_code == 302
    assert response.url == url

    redirected = admin_client.get(url)
    assert "ไม่สามารถบันทึกรอบที่พักได้" in redirected.content.decode()

    other.refresh_from_db()
    assert list(other.rooms.values_list("pk", flat=True)) == [lodging_data["rooms"][1].pk]


def test_manage_and_edit_routes_use_permissions_and_service(client, lodging_data):
    client.force_login(lodging_data["user"])
    manage = client.get(reverse("bookings:lodging_manage"))
    assert manage.status_code == 200
    start, end = _dates(offset=10)
    created = client.post(
        reverse("bookings:lodging_manage"),
        {
            "title": "สร้างจากหน้าเว็บ",
            "slug": "created-from-web",
            "check_in_date": start.isoformat(),
            "check_out_date": end.isoformat(),
            "beds_per_room": 4,
            "rooms": [str(lodging_data["rooms"][2].pk)],
        },
    )
    assert created.status_code == 302
    created_cohort = CourseLodgingCohort.objects.get(slug="created-from-web")
    assert created_cohort.allocation_status == CourseLodgingCohort.AllocationStatus.ALLOCATED
    assert created_cohort.is_active is True
    assert client.get(reverse("bookings:lodging_cohort_edit", args=[created_cohort.slug])).status_code == 200
    client.force_login(lodging_data["other"])
    assert client.get(reverse("bookings:lodging_cohort_edit", args=[created_cohort.slug])).status_code == 403


def test_seed_courses_is_idempotent_and_safe(lodging_data):
    output = StringIO()
    management.call_command("seed_courses", default_supervisor=lodging_data["user"].username, stdout=output)
    management.call_command("seed_courses", default_supervisor=lodging_data["user"].username, stdout=output)
    assert CourseLodgingCohort.objects.count() == 14
    assert CourseLodgingCohort.objects.filter(
        allocation_status=CourseLodgingCohort.AllocationStatus.RELEASED,
        is_active=False,
    ).count() == 14
    assert "นำเข้า/ตรวจสอบหลักสูตรครบ 14" in output.getvalue()

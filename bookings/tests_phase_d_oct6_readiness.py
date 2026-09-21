from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import threading

import pytest
from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connections
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from audit.models import AuditLog
from bookings.lodging_models import (
    CourseLodgingAccess,
    CourseLodgingCohort,
    CourseLodgingRelease,
    CourseStudentLodging,
    PublicLodgingThrottle,
)
from bookings.lodging_services import (
    assign_lodging_bed,
    check_in_student,
    release_lodging_reservation,
    request_general_lodging,
    set_cohort_self_booking,
)
from bookings.management.commands.seed_courses import COURSES
from bookings.models import Booking
from resources.models import Resource

pytestmark = pytest.mark.django_db

OCT6_SLUG = "jnr-nco-11"
OCT6_TITLE = "นายสิบชั้นต้น เหล่า ส. ผ่านสื่ออิเล็กทรอนิกส์(หลักสูตรเร่งรัด) รุ่นที่ 11"
OCT6_CHECK_IN = date(2026, 10, 6)
OCT6_CHECK_OUT = date(2026, 12, 25)


@pytest.fixture
def oct6_setup():
    unit = Unit.objects.create(code="OCT6", name="หน่วยทดสอบ 6 ต.ค.")
    supervisor = User.objects.create_user(
        username="oct6-supervisor",
        email="oct6-supervisor@signalschool.ac.th",
        password="test-pass-2026",
        unit=unit,
    )
    outsider = User.objects.create_user(
        username="oct6-outsider",
        email="oct6-outsider@signalschool.ac.th",
        password="test-pass-2026",
        unit=unit,
    )
    rooms = [
        Resource.objects.create(
            code=f"OCT6-{number}",
            name=f"ห้องพัก OCT6 {number}",
            building="อาคารพักทดสอบ",
            floor=4,
            resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.LODGING,
            status=Resource.Status.ACTIVE,
        )
        for number in (401, 402)
    ]
    public_room = Resource.objects.create(
        code="OCT6-PUBLIC",
        name="ห้องพักบุคคลทั่วไป OCT6",
        building="อาคารพักทดสอบ",
        floor=5,
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        status=Resource.Status.ACTIVE,
    )
    now = timezone.now()
    cohort = CourseLodgingCohort.objects.create(
        title=OCT6_TITLE,
        slug=OCT6_SLUG,
        supervisor=supervisor,
        unit=unit,
        check_in_date=OCT6_CHECK_IN,
        check_out_date=OCT6_CHECK_OUT,
        beds_per_room=2,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
        booking_open_at=now - timedelta(hours=1),
        booking_close_at=now + timedelta(days=10),
    )
    cohort.rooms.add(*rooms)
    return {
        "unit": unit,
        "supervisor": supervisor,
        "outsider": outsider,
        "rooms": rooms,
        "public_room": public_room,
        "cohort": cohort,
    }


def _self_book(data, *, room_index=0, bed=1, phone="0811111111", name="นักเรียนทดสอบ"):
    return assign_lodging_bed(
        cohort=data["cohort"],
        room_id=data["rooms"][room_index].pk,
        bed_number=bed,
        rank="ส.อ.",
        full_name=name,
        origin_unit="ส.พัน.ทดสอบ",
        phone=phone,
        actor=None,
    )


def _staff_book(data, *, room_index=0, bed=1, phone="0822222222", name="ผู้พักเจ้าหน้าที่จัด"):
    return assign_lodging_bed(
        cohort=data["cohort"],
        room_id=data["rooms"][room_index].pk,
        bed_number=bed,
        rank="ส.อ.",
        full_name=name,
        origin_unit="ส.พัน.ทดสอบ",
        phone=phone,
        actor=data["supervisor"],
    )


def test_seed_source_of_truth_contains_exact_oct6_course():
    row = next(item for item in COURSES if item[1] == OCT6_SLUG)
    assert row == (OCT6_TITLE, OCT6_SLUG, "2026-10-06", "2026-12-25")


def test_self_booking_gets_private_management_capability_and_public_pass_does_not_expose_it(client, oct6_setup):
    student = _self_book(oct6_setup)
    access = CourseLodgingAccess.objects.get(student=student)

    manage_url = reverse("bookings:lodging_reservation_manage", args=[OCT6_SLUG, access.pk])
    response = client.get(manage_url)
    assert response.status_code == 200
    html = response.content.decode()
    assert "จัดการการจองของฉัน" in html
    assert reverse("bookings:lodging_reservation_cancel", args=[OCT6_SLUG, access.pk]) in html
    assert response.headers["Referrer-Policy"] == "no-referrer"

    pass_url = reverse("bookings:lodging_pass", args=[OCT6_SLUG, student.pk])
    public_pass = client.get(pass_url)
    public_html = public_pass.content.decode()
    assert str(access.pk) not in public_html
    assert "ยกเลิกการจองและคืนเตียง" not in public_html
    assert str(student.pk) in html
    assert "window.location.href" not in html


def test_self_cancel_frees_bed_preserves_history_and_allows_rebook(client, oct6_setup):
    student = _self_book(oct6_setup, phone="0812223333")
    access = student.self_service_access
    cancel_url = reverse("bookings:lodging_reservation_cancel", args=[OCT6_SLUG, access.pk])

    response = client.post(cancel_url)
    assert response.status_code == 302
    assert response.url == reverse("bookings:lodging_portal", args=[OCT6_SLUG])
    assert not CourseStudentLodging.objects.filter(pk=student.pk).exists()

    release = CourseLodgingRelease.objects.get(original_student_id=student.pk)
    assert release.outcome == CourseLodgingRelease.Outcome.CANCELLED
    assert release.channel == CourseLodgingRelease.Channel.SELF_SERVICE
    assert release.phone == "0812223333"
    assert AuditLog.objects.filter(
        entity_id=str(student.pk), action="lodging_reservation_cancelled"
    ).exists()

    rebooked = _self_book(oct6_setup, room_index=1, bed=1, phone="0812223333", name="นักเรียนจองใหม่")
    assert rebooked.pk != student.pk
    assert rebooked.room_id == oct6_setup["rooms"][1].pk


def test_self_cancel_is_blocked_after_booking_window_closes(oct6_setup):
    student = _self_book(oct6_setup, phone="0813334444")
    token = student.self_service_access.pk
    CourseLodgingCohort.objects.filter(pk=oct6_setup["cohort"].pk).update(
        booking_close_at=timezone.now() - timedelta(minutes=1)
    )
    oct6_setup["cohort"].refresh_from_db()

    with pytest.raises(ValidationError, match="ยกเลิกด้วยตนเองไม่ได้"):
        release_lodging_reservation(
            student=student,
            outcome=CourseLodgingRelease.Outcome.CANCELLED,
            access_token=token,
        )
    assert CourseStudentLodging.objects.filter(pk=student.pk).exists()


def test_no_show_is_staff_only_not_before_oct6_and_releases_inventory(oct6_setup):
    student = _staff_book(oct6_setup, phone="0823334444")
    before_arrival = timezone.make_aware(
        timezone.datetime(2026, 10, 5, 12, 0), timezone.get_current_timezone()
    )
    on_arrival = timezone.make_aware(
        timezone.datetime(2026, 10, 6, 18, 0), timezone.get_current_timezone()
    )

    with pytest.raises(ValidationError, match="ยังไม่ถึงวันเข้าพัก"):
        release_lodging_reservation(
            student=student,
            outcome=CourseLodgingRelease.Outcome.NO_SHOW,
            actor=oct6_setup["supervisor"],
            now=before_arrival,
        )
    with pytest.raises(PermissionDenied):
        release_lodging_reservation(
            student=student,
            outcome=CourseLodgingRelease.Outcome.NO_SHOW,
            actor=oct6_setup["outsider"],
            now=on_arrival,
        )

    release = release_lodging_reservation(
        student=student,
        outcome=CourseLodgingRelease.Outcome.NO_SHOW,
        actor=oct6_setup["supervisor"],
        now=on_arrival,
        reason="ไม่มารายงานตัวตามกำหนด",
    )
    assert release.outcome == CourseLodgingRelease.Outcome.NO_SHOW
    assert release.released_by_id == oct6_setup["supervisor"].pk
    assert not CourseStudentLodging.objects.filter(pk=student.pk).exists()
    assert AuditLog.objects.filter(entity_id=str(student.pk), action="lodging_no_show").exists()


def test_checkin_blocks_early_allows_on_time_and_late_then_blocks_after_checkout(oct6_setup):
    early_student = _staff_book(oct6_setup, bed=1, phone="0831111111", name="ก่อนเวลา")
    ontime_student = _staff_book(oct6_setup, bed=2, phone="0832222222", name="ตรงเวลา")
    late_student = _staff_book(oct6_setup, room_index=1, bed=1, phone="0833333333", name="มาช้า")
    expired_student = _staff_book(oct6_setup, room_index=1, bed=2, phone="0834444444", name="หลังจบ")

    early = timezone.make_aware(timezone.datetime(2026, 10, 5, 23, 59), timezone.get_current_timezone())
    ontime = timezone.make_aware(timezone.datetime(2026, 10, 6, 8, 0), timezone.get_current_timezone())
    late = timezone.make_aware(timezone.datetime(2026, 10, 10, 20, 0), timezone.get_current_timezone())
    expired = timezone.make_aware(timezone.datetime(2026, 12, 26, 0, 1), timezone.get_current_timezone())

    with pytest.raises(ValidationError, match="ยังไม่ถึงวันเข้าพัก"):
        check_in_student(early_student, oct6_setup["supervisor"], now=early)
    assert check_in_student(ontime_student, oct6_setup["supervisor"], now=ontime).checked_in_at == ontime
    assert check_in_student(late_student, oct6_setup["supervisor"], now=late).checked_in_at == late
    with pytest.raises(ValidationError, match="รอบเข้าพักสิ้นสุดแล้ว"):
        check_in_student(expired_student, oct6_setup["supervisor"], now=expired)


def test_staff_close_midway_blocks_new_direct_self_booking(oct6_setup):
    first = _self_book(oct6_setup, phone="0841111111")
    assert first.pk
    set_cohort_self_booking(cohort=oct6_setup["cohort"], actor=oct6_setup["supervisor"], enabled=False)
    oct6_setup["cohort"].refresh_from_db()

    with pytest.raises(ValidationError, match="ปิดรับจอง"):
        _self_book(oct6_setup, bed=2, phone="0842222222", name="หลังเจ้าหน้าที่ปิด")


def test_public_request_is_idempotent_for_exact_duplicate(oct6_setup):
    room = oct6_setup["public_room"]
    check_in = timezone.localdate() + timedelta(days=1)
    kwargs = dict(
        room=room,
        check_in=check_in,
        check_out=check_in + timedelta(days=1),
        phone="0851112222",
        guest_name="ผู้เข้าพักทั่วไป",
        client_key="browser-a",
    )
    first = request_general_lodging(**kwargs)
    assert first.pk
    with pytest.raises(ValidationError, match="มีคำขอเข้าพักช่วงนี้"):
        request_general_lodging(**kwargs)
    assert Booking.objects.filter(title="คำขอเข้าพักทั่วไป", responsible_phone="0851112222").count() == 1


def test_duplicate_public_post_does_not_disclose_existing_status_token(client, oct6_setup):
    room = oct6_setup["public_room"]
    check_in = timezone.localdate() + timedelta(days=1)
    payload = {
        "guest_name": "ผู้เข้าพักทั่วไป",
        "room": str(room.pk),
        "check_in": check_in.isoformat(),
        "check_out": (check_in + timedelta(days=1)).isoformat(),
        "phone": "0859998888",
        "note": "",
    }
    first = client.post(reverse("bookings:lodging_general_request"), payload)
    assert first.status_code == 302
    booking = Booking.objects.get(responsible_phone="0859998888")
    token = booking.public_lodging_access.pk
    assert str(token) in first.url

    duplicate = client.post(reverse("bookings:lodging_general_request"), payload)
    assert duplicate.status_code == 200
    html = duplicate.content.decode()
    assert "มีคำขอเข้าพักช่วงนี้ด้วยเบอร์โทรนี้อยู่แล้ว" in html
    assert str(token) not in html
    assert Booking.objects.filter(responsible_phone="0859998888").count() == 1


def test_public_request_phone_rate_limit_is_persistent_and_hashes_identifier(settings, oct6_setup):
    settings.PUBLIC_LODGING_RATE_PHONE_LIMIT = 2
    settings.PUBLIC_LODGING_RATE_CLIENT_LIMIT = 99
    room = oct6_setup["public_room"]
    base = timezone.localdate() + timedelta(days=1)

    for offset in (0, 2):
        request_general_lodging(
            room=room,
            check_in=base + timedelta(days=offset),
            check_out=base + timedelta(days=offset + 1),
            phone="0861112222",
            guest_name="ผู้เข้าพักทั่วไป",
            client_key="browser-rate",
        )
    with pytest.raises(ValidationError, match="ส่งคำขอถี่เกินไป"):
        request_general_lodging(
            room=room,
            check_in=base + timedelta(days=4),
            check_out=base + timedelta(days=5),
            phone="0861112222",
            guest_name="ผู้เข้าพักทั่วไป",
            client_key="browser-rate",
        )

    phone_rows = PublicLodgingThrottle.objects.filter(scope=PublicLodgingThrottle.Scope.PHONE)
    assert phone_rows.count() == 1
    assert phone_rows.get().count == 2
    assert phone_rows.get().key_hash != "0861112222"
    assert len(phone_rows.get().key_hash) == 64


def test_anonymous_user_cannot_access_staff_workspace(client):
    response = client.get(reverse("bookings:lodging_workspace"))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db(transaction=True)
def test_concurrent_last_bed_allows_exactly_one_winner(oct6_setup):
    cohort = oct6_setup["cohort"]
    room = oct6_setup["rooms"][0]
    CourseLodgingCohort.objects.filter(pk=cohort.pk).update(beds_per_room=1)
    cohort.refresh_from_db()
    barrier = threading.Barrier(2)

    def attempt(index):
        close_old_connections()
        try:
            local_cohort = CourseLodgingCohort.objects.get(pk=cohort.pk)
            barrier.wait(timeout=5)
            assign_lodging_bed(
                cohort=local_cohort,
                room_id=room.pk,
                bed_number=1,
                rank="ส.อ.",
                full_name=f"พร้อมกัน {index}",
                origin_unit="ส.พัน.ทดสอบ",
                phone=f"087000000{index}",
                actor=None,
            )
            return "won"
        except (ValidationError, IntegrityError):
            return "blocked"
        finally:
            connections["default"].close()
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, (1, 2)))

    assert sorted(results) == ["blocked", "won"]
    assert CourseStudentLodging.objects.filter(cohort=cohort, room=room, bed_number=1).count() == 1


def test_admin_cannot_bypass_lodging_release_services(rf, oct6_setup):
    request = rf.get("/admin/")
    request.user = oct6_setup["supervisor"]
    student_admin = admin.site._registry[CourseStudentLodging]
    release_admin = admin.site._registry[CourseLodgingRelease]

    assert student_admin.has_add_permission(request) is False
    assert student_admin.has_change_permission(request) is False
    assert student_admin.has_delete_permission(request) is False
    assert release_admin.has_add_permission(request) is False
    assert release_admin.has_change_permission(request) is False
    assert release_admin.has_delete_permission(request) is False


def test_workspace_surfaces_no_show_history(client, oct6_setup):
    student = _staff_book(oct6_setup, phone="0881112222")
    arrival = timezone.make_aware(timezone.datetime(2026, 10, 6, 19, 0), timezone.get_current_timezone())
    release_lodging_reservation(
        student=student,
        outcome=CourseLodgingRelease.Outcome.NO_SHOW,
        actor=oct6_setup["supervisor"],
        now=arrival,
    )
    client.force_login(oct6_setup["supervisor"])
    response = client.get(reverse("bookings:lodging_workspace") + f"?cohort={OCT6_SLUG}")
    assert response.status_code == 200
    assert response.context["operations_summary"]["no_show"] == 1
    assert "ไม่มารายงานตัวสะสม" in response.content.decode()

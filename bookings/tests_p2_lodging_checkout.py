from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from audit.models import AuditLog
from bookings.lodging_models import (
    CourseLodgingAccess,
    CourseLodgingCohort,
    CourseLodgingRelease,
    CourseStudentLodging,
)
from bookings.lodging_services import check_in_student, release_lodging_reservation
from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def stay():
    staff = User.objects.create_user(username="checkout-staff", email="checkout-staff@example.test")
    outsider = User.objects.create_user(username="checkout-outsider", email="checkout-outsider@example.test")
    room = Resource.objects.create(
        code="CHECKOUT-401",
        name="ห้องพักทดสอบเช็กเอาต์",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        status=Resource.Status.ACTIVE,
    )
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรทดสอบเช็กเอาต์",
        slug="checkout-test",
        supervisor=staff,
        check_in_date=today,
        check_out_date=today + timedelta(days=2),
        beds_per_room=2,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    cohort.rooms.add(room)
    student = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=1,
        rank="ร.ต.",
        full_name="ผู้พักทดสอบเช็กเอาต์",
        origin_unit="หน่วยทดสอบ",
        phone="0812345678",
    )
    access = CourseLodgingAccess.objects.create(student=student)
    return staff, outsider, cohort, room, student, access


def test_checked_out_preserves_checkin_history_audit_and_releases_bed(stay):
    staff, _, cohort, room, student, access = stay
    checked_in = check_in_student(student, staff)

    release = release_lodging_reservation(
        student=student,
        outcome=CourseLodgingRelease.Outcome.CHECKED_OUT,
        actor=staff,
        reason="ครบกำหนดการเข้าพัก",
    )

    assert release.outcome == CourseLodgingRelease.Outcome.CHECKED_OUT
    assert release.channel == CourseLodgingRelease.Channel.STAFF
    assert release.reason == "ครบกำหนดการเข้าพัก"
    assert release.checked_in_at == checked_in.checked_in_at
    assert release.checked_in_by_id == staff.pk
    assert release.released_by_id == staff.pk
    assert release.room_id == room.pk and release.bed_number == 1
    assert not cohort.students.filter(pk=student.pk).exists()
    assert not CourseLodgingAccess.objects.filter(pk=access.pk).exists()
    assert cohort.beds_per_room - cohort.students.filter(room=room).count() == 2
    assert AuditLog.objects.filter(entity_id=str(student.pk), action="student_checked_in").exists()
    assert AuditLog.objects.filter(entity_id=str(student.pk), action="lodging_checked_out").exists()


def test_checkout_requires_checkin_staff_permission_and_reason(stay):
    staff, outsider, _, _, student, _ = stay
    with pytest.raises(ValidationError, match="ยังไม่รายงานตัว"):
        release_lodging_reservation(
            student=student,
            outcome=CourseLodgingRelease.Outcome.CHECKED_OUT,
            actor=staff,
            reason="ออกแล้ว",
        )

    check_in_student(student, staff)
    with pytest.raises(PermissionDenied):
        release_lodging_reservation(
            student=student,
            outcome=CourseLodgingRelease.Outcome.CHECKED_OUT,
            actor=outsider,
            reason="ออกแล้ว",
        )
    with pytest.raises(PermissionDenied):
        release_lodging_reservation(
            student=student,
            outcome=CourseLodgingRelease.Outcome.CHECKED_OUT,
            reason="ออกแล้ว",
        )
    with pytest.raises(ValidationError, match="เหตุผล"):
        release_lodging_reservation(
            student=student,
            outcome=CourseLodgingRelease.Outcome.CHECKED_OUT,
            actor=staff,
            reason="  ",
        )
    with pytest.raises(ValidationError, match="300"):
        release_lodging_reservation(
            student=student,
            outcome=CourseLodgingRelease.Outcome.CHECKED_OUT,
            actor=staff,
            reason="ย" * 301,
        )
    for outcome in (CourseLodgingRelease.Outcome.CANCELLED, CourseLodgingRelease.Outcome.NO_SHOW):
        with pytest.raises(ValidationError, match="ขั้นตอนออกจากที่พัก"):
            release_lodging_reservation(student=student, outcome=outcome, actor=staff)
    assert CourseStudentLodging.objects.filter(pk=student.pk).exists()
    assert not CourseLodgingRelease.objects.filter(original_student_id=student.pk).exists()


def test_checked_in_guest_can_checkout_after_cohort_end(stay):
    staff, _, _, _, student, _ = stay
    check_in_student(student, staff)

    release = release_lodging_reservation(
        student=student,
        outcome=CourseLodgingRelease.Outcome.CHECKED_OUT,
        actor=staff,
        reason="ปิดรายการตกค้างหลังจบหลักสูตร",
        now=timezone.now() + timedelta(days=4),
    )

    assert release.checked_in_at is not None
    assert release.outcome == CourseLodgingRelease.Outcome.CHECKED_OUT


def test_staff_workspace_checkout_is_one_time_and_stale_links_close(client, stay):
    staff, outsider, cohort, _, student, access = stay
    check_in_student(student, staff)
    workspace = reverse("bookings:lodging_workspace") + f"?cohort={cohort.slug}"
    cancel_url = reverse("bookings:lodging_reservation_cancel", args=[cohort.slug, access.pk])
    manage_url = reverse("bookings:lodging_reservation_manage", args=[cohort.slug, access.pk])
    pass_url = reverse("bookings:lodging_pass", args=[cohort.slug, student.pk])

    client.force_login(outsider)
    assert client.post(workspace, {"action": "release_student", "student_id": student.pk,
                                   "outcome": "checked_out", "reason": "ออกแล้ว"}).status_code == 403
    client.logout()
    assert client.post(cancel_url).status_code == 302
    assert CourseStudentLodging.objects.filter(pk=student.pk).exists()

    client.force_login(staff)
    page = client.get(workspace)
    assert page.status_code == 200
    assert "บันทึกออกจากที่พัก" in page.content.decode()
    assert f'checkout-reason-{student.pk}' in page.content.decode()
    data = {"action": "release_student", "student_id": student.pk,
            "outcome": "checked_out", "reason": "กลับหน่วยต้นสังกัด"}
    assert client.post(workspace, data).status_code == 302
    assert client.post(workspace, data).status_code == 200
    assert CourseLodgingRelease.objects.filter(original_student_id=student.pk).count() == 1
    assert not CourseStudentLodging.objects.filter(pk=student.pk).exists()
    assert client.get(manage_url).status_code == 404
    assert client.get(pass_url).status_code == 404

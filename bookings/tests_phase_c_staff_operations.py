from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from audit.models import AuditLog
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from bookings.lodging_services import move_lodging_bed, request_general_lodging
from bookings.models import Booking
from resources.models import Resource, ResourceApprover

pytestmark = pytest.mark.django_db


@pytest.fixture
def operations_data():
    unit = Unit.objects.create(code="OPSC", name="หน่วย Staff Operations")
    staff = User.objects.create_user(username="ops-staff", email="ops-staff@example.test", unit=unit)
    outsider = User.objects.create_user(username="ops-outsider", email="ops-outsider@example.test", unit=unit)
    approval_only = User.objects.create_user(username="ops-approval-only", email="ops-approval@example.test", unit=unit)

    public_room = Resource.objects.create(
        code="OPS-GUEST",
        name="ห้องพักบุคคลทั่วไป",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        status=Resource.Status.ACTIVE,
    )
    ResourceApprover.objects.create(resource=public_room, user=staff, is_primary=True)
    ResourceApprover.objects.create(resource=public_room, user=approval_only, is_primary=False)

    course_rooms = [
        Resource.objects.create(
            code=f"OPS-{number}",
            name=f"ห้องพักหลักสูตร {number}",
            resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.LODGING,
            status=Resource.Status.ACTIVE,
        )
        for number in (401, 402)
    ]
    start = timezone.localdate() + timedelta(days=10)
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตร Staff Operations",
        slug="staff-ops",
        supervisor=staff,
        unit=unit,
        check_in_date=start,
        check_out_date=start + timedelta(days=3),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
        booking_open_at=timezone.now() - timedelta(hours=1),
        booking_close_at=timezone.now() + timedelta(days=2),
        beds_per_room=2,
    )
    cohort.rooms.add(*course_rooms)
    pending_student = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=course_rooms[0],
        bed_number=1,
        rank="ร.ท.",
        full_name="ผู้พักรอย้าย",
        origin_unit="หน่วย Staff Operations",
        phone="0811111111",
    )
    checked_student = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=course_rooms[1],
        bed_number=1,
        rank="ร.อ.",
        full_name="ผู้พักมาแล้ว",
        origin_unit="หน่วย Staff Operations",
        phone="0822222222",
        checked_in_at=timezone.now(),
        checked_in_by=staff,
    )
    public_booking = request_general_lodging(
        room=public_room,
        check_in=start + timedelta(days=5),
        check_out=start + timedelta(days=6),
        phone="0899999999",
        guest_name="ผู้เข้าพักทั่วไป",
        note="ทดสอบ Phase C",
    )
    return {
        "unit": unit,
        "staff": staff,
        "outsider": outsider,
        "approval_only": approval_only,
        "public_room": public_room,
        "course_rooms": course_rooms,
        "cohort": cohort,
        "pending_student": pending_student,
        "checked_student": checked_student,
        "public_booking": public_booking,
    }


def _workspace_url():
    return reverse("bookings:lodging_workspace") + "?cohort=staff-ops"


def test_staff_workspace_starts_with_actionable_operations_summary(client, operations_data):
    client.force_login(operations_data["staff"])
    response = client.get(_workspace_url())

    assert response.status_code == 200
    assert response.context["operations_summary"] == {
        "public_pending": 1,
        "open_courses": 1,
        "assigned": 2,
        "free_beds": 2,
        "pending_arrivals": 1,
    }
    assert [item.pk for item in response.context["public_pending_requests"]] == [
        operations_data["public_booking"].pk
    ]
    html = response.content.decode()
    assert "คำขอทั่วไปที่รออนุมัติ" in html
    assert "ผู้เข้าพักทั่วไป" in html
    assert "สถานะรอบที่พัก" in html
    assert "ย้ายเตียง" in html
    assert "private" in response.headers["Cache-Control"]
    assert "no-store" in response.headers["Cache-Control"]


def test_public_request_can_be_approved_from_dashboard_permission_boundary(client, operations_data):
    booking = operations_data["public_booking"]
    client.force_login(operations_data["staff"])
    response = client.post(
        reverse("approvals:approve", args=[booking.pk]),
        {"next": _workspace_url()},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == _workspace_url()
    booking.refresh_from_db()
    assert booking.request_status == Booking.RequestStatus.APPROVED


def test_quick_booking_toggle_closes_and_reopens_without_changing_allocation(client, operations_data):
    cohort = operations_data["cohort"]
    original_rooms = set(cohort.rooms.values_list("pk", flat=True))
    client.force_login(operations_data["staff"])

    closed = client.post(
        _workspace_url(),
        {"action": "booking_toggle", "booking_state": "closed"},
    )
    assert closed.status_code == 302
    cohort.refresh_from_db()
    assert cohort.is_active is False
    assert set(cohort.rooms.values_list("pk", flat=True)) == original_rooms

    reopened = client.post(
        _workspace_url(),
        {"action": "booking_toggle", "booking_state": "open"},
    )
    assert reopened.status_code == 302
    cohort.refresh_from_db()
    assert cohort.is_active is True
    assert cohort.booking_open_at is not None
    assert cohort.booking_close_at is not None
    assert set(cohort.rooms.values_list("pk", flat=True)) == original_rooms


def test_staff_can_move_guest_to_free_bed_from_workspace_and_audit_is_written(client, operations_data):
    student = operations_data["pending_student"]
    target_room = operations_data["course_rooms"][1]
    client.force_login(operations_data["staff"])

    response = client.post(
        _workspace_url(),
        {
            "action": "move_bed",
            "student_id": str(student.pk),
            "target": f"{target_room.pk}:2",
        },
    )
    assert response.status_code == 302
    student.refresh_from_db()
    assert student.room_id == target_room.pk
    assert student.bed_number == 2
    assert AuditLog.objects.filter(
        entity="bookings.coursestudentlodging",
        entity_id=str(student.pk),
        action="lodging_bed_moved",
    ).exists()


def test_move_to_occupied_bed_is_rejected_without_mutating_guest(client, operations_data):
    student = operations_data["pending_student"]
    occupied = operations_data["checked_student"]
    original_room_id = student.room_id
    original_bed = student.bed_number
    client.force_login(operations_data["staff"])

    response = client.post(
        _workspace_url(),
        {
            "action": "move_bed",
            "student_id": str(student.pk),
            "target": f"{occupied.room_id}:{occupied.bed_number}",
        },
    )
    assert response.status_code == 200
    student.refresh_from_db()
    assert student.room_id == original_room_id
    assert student.bed_number == original_bed
    assert response.context["move_form"].errors.get("target")


def test_move_service_rejects_user_without_cohort_permission(operations_data):
    with pytest.raises(PermissionDenied):
        move_lodging_bed(
            student=operations_data["pending_student"],
            room_id=operations_data["course_rooms"][1].pk,
            bed_number=2,
            actor=operations_data["outsider"],
        )

def test_lodging_approver_can_open_operations_without_course_management_leak(client, operations_data):
    client.force_login(operations_data["approval_only"])
    response = client.get(reverse("bookings:lodging_workspace"))

    assert response.status_code == 200
    assert list(response.context["cohorts"]) == []
    assert response.context["cohort"] is None
    assert response.context["operations_summary"]["assigned"] == 0
    assert response.context["operations_summary"]["free_beds"] == 0
    assert response.context["can_manage_course_operations"] is False
    assert "จัดสรรห้อง / สร้างหลักสูตร" not in response.content.decode()

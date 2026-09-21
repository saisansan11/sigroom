from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def arrival_data():
    unit = Unit.objects.create(code="UX31", name="หน่วย UX31")
    staff = User.objects.create_user(username="ux31-staff", email="ux31-staff@example.test", unit=unit)
    outsider = User.objects.create_user(username="ux31-outsider", email="ux31-outsider@example.test", unit=unit)
    rooms = [
        Resource.objects.create(
            code=f"UX31-{number}",
            name=f"ห้องพัก UX31 {number}",
            resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.LODGING,
            status=Resource.Status.ACTIVE,
        )
        for number in (401, 402, 403)
    ]
    start = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตร UX31",
        slug="ux31",
        supervisor=staff,
        check_in_date=start,
        check_out_date=start + timedelta(days=4),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=False,
        beds_per_room=2,
    )
    cohort.rooms.add(*rooms)
    checked = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=rooms[0],
        bed_number=1,
        rank="ร.ต.",
        full_name="ผู้พักมาแล้ว",
        origin_unit="หน่วย UX31",
        phone="0811111111",
        checked_in_at=timezone.now(),
        checked_in_by=staff,
    )
    pending_one = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=rooms[1],
        bed_number=1,
        rank="ร.ท.",
        full_name="ผู้พักรอหนึ่ง",
        origin_unit="หน่วย UX31",
        phone="0822222222",
    )
    pending_two = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=rooms[1],
        bed_number=2,
        rank="ร.อ.",
        full_name="ผู้พักรอสอง",
        origin_unit="หน่วย UX31",
        phone="0833333333",
    )
    return staff, outsider, rooms, cohort, checked, pending_one, pending_two


def _workspace_url(room_filter="all", arrival_filter="all"):
    return (
        reverse("bookings:lodging_workspace")
        + f"?cohort=ux31&room_filter={room_filter}&arrival_filter={arrival_filter}"
    )


def _room_codes(response):
    return [item["room"].code for item in response.context["rooms"]]


def test_arrival_summary_and_filters_use_existing_student_state(client, arrival_data):
    staff, _, rooms, _, _, _, _ = arrival_data
    client.force_login(staff)

    response = client.get(_workspace_url())
    assert response.status_code == 200
    assert response.context["arrival"] == {"pending": 2, "checked_in": 1}
    html = response.content.decode()
    assert "รอรายงานตัว" in html
    assert "รายงานตัวแล้ว" in html

    pending = client.get(_workspace_url(arrival_filter="pending"))
    assert pending.context["arrival_filter"] == "pending"
    assert _room_codes(pending) == [rooms[1].code]

    checked = client.get(_workspace_url(arrival_filter="checked_in"))
    assert checked.context["arrival_filter"] == "checked_in"
    assert _room_codes(checked) == [rooms[0].code]


def test_arrival_filter_composes_with_room_filter_and_falls_back_safely(client, arrival_data):
    staff, _, rooms, _, _, _, _ = arrival_data
    client.force_login(staff)

    pending_free = client.get(_workspace_url(room_filter="free", arrival_filter="pending"))
    assert _room_codes(pending_free) == []
    assert "ไม่มีห้องในตัวกรองนี้" in pending_free.content.decode()
    assert len(pending_free.context["form"].fields["room_id"].choices) == 3

    invalid = client.get(_workspace_url(arrival_filter="tampered"))
    assert invalid.context["arrival_filter"] == "all"
    assert _room_codes(invalid) == [room.code for room in rooms]
    assert 'arrival_filter=all#room-board" aria-current="page"' in invalid.content.decode()


def test_pending_beds_link_to_existing_checkin_route_and_bed_first_keeps_filters(client, arrival_data):
    staff, _, rooms, _, checked, pending_one, pending_two = arrival_data
    client.force_login(staff)

    response = client.get(_workspace_url(arrival_filter="pending"))
    html = response.content.decode()
    assert html.count("ตรวจรับรายงานตัว") == 2
    assert reverse("bookings:lodging_checkin", args=[pending_one.id]) + "?from_workspace=1" in html
    assert reverse("bookings:lodging_checkin", args=[pending_two.id]) + "?from_workspace=1" in html
    assert reverse("bookings:lodging_checkin", args=[checked.id]) + "?from_workspace=1" not in html
    assert "✓ รายงานตัวแล้ว" not in html

    all_response = client.get(_workspace_url(room_filter="free", arrival_filter="all"))
    all_html = all_response.content.decode()
    assert f"room_filter=free&amp;room={rooms[0].pk}&amp;bed=2#assign-heading" in all_html


def test_workspace_checkin_return_is_staff_only_and_post_preserves_safe_context(client, arrival_data):
    staff, outsider, _, cohort, _, pending_one, _ = arrival_data
    checkin_url = reverse("bookings:lodging_checkin", args=[pending_one.id]) + "?from_workspace=1"

    client.force_login(staff)
    response = client.get(checkin_url)
    assert response.status_code == 200
    expected_return = (
        reverse("bookings:lodging_workspace")
        + f"?cohort={cohort.slug}&arrival_filter=pending#room-board"
    )
    assert response.context["workspace_return_url"] == expected_return
    assert "กลับผังและดูผู้รอรายงานตัว" in response.content.decode()

    post = client.post(checkin_url)
    assert post.status_code == 302
    assert post.headers["Location"].endswith(f"/lodging/checkin/{pending_one.id}/?from_workspace=1")
    pending_one.refresh_from_db()
    assert pending_one.checked_in_at is not None
    assert pending_one.checked_in_by_id == staff.id

    client.force_login(outsider)
    public_like = client.get(checkin_url)
    assert public_like.status_code == 200
    assert public_like.context["workspace_return_url"] is None
    assert "กลับผังและดูผู้รอรายงานตัว" not in public_like.content.decode()

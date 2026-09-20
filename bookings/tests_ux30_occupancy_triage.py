from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def occupancy_data():
    unit = Unit.objects.create(code="UX30", name="หน่วย UX30")
    staff = User.objects.create_user(username="ux30-staff", unit=unit)
    rooms = [
        Resource.objects.create(
            code=f"UX30-{number}",
            name=f"ห้องพัก UX30 {number}",
            resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.LODGING,
            status=Resource.Status.ACTIVE,
        )
        for number in (401, 402, 403)
    ]
    start = timezone.localdate() + timedelta(days=7)
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตร UX30",
        slug="ux30",
        supervisor=staff,
        check_in_date=start,
        check_out_date=start + timedelta(days=4),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=False,
        beds_per_room=2,
    )
    cohort.rooms.add(*rooms)
    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=rooms[0],
        bed_number=1,
        rank="ร.ต.",
        full_name="ผู้พักหนึ่ง",
        origin_unit="หน่วย UX30",
        phone="0811111111",
        checked_in_at=timezone.now(),
        checked_in_by=staff,
    )
    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=rooms[1],
        bed_number=1,
        rank="ร.ท.",
        full_name="ผู้พักสอง",
        origin_unit="หน่วย UX30",
        phone="0822222222",
    )
    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=rooms[1],
        bed_number=2,
        rank="ร.อ.",
        full_name="ผู้พักสาม",
        origin_unit="หน่วย UX30",
        phone="0833333333",
    )
    return staff, rooms, cohort


def _workspace_url(room_filter=None):
    url = reverse("bookings:lodging_workspace") + "?cohort=ux30"
    if room_filter is not None:
        url += f"&room_filter={room_filter}"
    return url


def _room_codes(response):
    return [item["room"].code for item in response.context["rooms"]]


def test_occupancy_summary_matches_room_board(client, occupancy_data):
    staff, _, _ = occupancy_data
    client.force_login(staff)

    response = client.get(_workspace_url())
    assert response.status_code == 200
    assert response.context["occupancy"] == {
        "capacity": 6,
        "assigned": 3,
        "free_beds": 3,
        "checked_in": 1,
        "rooms_total": 3,
        "rooms_free": 2,
        "rooms_full": 1,
    }
    html = response.content.decode()
    assert "จัดแล้ว / 6 เตียง" in html
    assert "เตียงว่าง" in html
    assert "รายงานตัวแล้ว" in html
    assert "ห้องที่จัดสรร" in html


def test_room_filter_shows_free_and_full_rooms_without_changing_form_choices(client, occupancy_data):
    staff, rooms, _ = occupancy_data
    client.force_login(staff)

    free_response = client.get(_workspace_url("free"))
    assert free_response.context["room_filter"] == "free"
    assert _room_codes(free_response) == [rooms[0].code, rooms[2].code]
    assert len(free_response.context["form"].fields["room_id"].choices) == 3

    full_response = client.get(_workspace_url("full"))
    assert full_response.context["room_filter"] == "full"
    assert _room_codes(full_response) == [rooms[1].code]
    assert len(full_response.context["form"].fields["room_id"].choices) == 3

    all_response = client.get(_workspace_url("all"))
    assert _room_codes(all_response) == [room.code for room in rooms]


def test_invalid_room_filter_falls_back_to_all(client, occupancy_data):
    staff, rooms, _ = occupancy_data
    client.force_login(staff)

    response = client.get(_workspace_url("tampered"))
    assert response.status_code == 200
    assert response.context["room_filter"] == "all"
    assert _room_codes(response) == [room.code for room in rooms]
    html = response.content.decode()
    assert 'room_filter=all#room-board" aria-current="page"' in html


def test_free_filter_preserves_bed_first_context_and_privacy_headers(client, occupancy_data):
    staff, rooms, _ = occupancy_data
    client.force_login(staff)

    response = client.get(_workspace_url("free"))
    html = response.content.decode()
    assert f"room_filter=free&amp;room={rooms[0].pk}&amp;bed=2#assign-heading" in html
    assert f"room_filter=free&amp;room={rooms[2].pk}&amp;bed=1#assign-heading" in html
    assert "private" in response.headers["Cache-Control"]
    assert "no-store" in response.headers["Cache-Control"]


def test_unallocated_cohort_uses_distinct_empty_state_without_room_filters(client, occupancy_data):
    staff, _, cohort = occupancy_data
    empty = CourseLodgingCohort.objects.create(
        title="หลักสูตรยังไม่จัดห้อง",
        slug="ux30-empty",
        supervisor=staff,
        check_in_date=cohort.check_in_date,
        check_out_date=cohort.check_out_date,
        allocation_status=CourseLodgingCohort.AllocationStatus.RELEASED,
        is_active=False,
        beds_per_room=2,
    )
    client.force_login(staff)

    response = client.get(reverse("bookings:lodging_workspace") + "?cohort=ux30-empty")
    html = response.content.decode()
    assert response.status_code == 200
    assert response.context["occupancy"]["rooms_total"] == 0
    assert "ยังไม่ได้จัดสรรห้องให้หลักสูตรนี้" in html
    assert 'class="lodging-room-filters"' not in html

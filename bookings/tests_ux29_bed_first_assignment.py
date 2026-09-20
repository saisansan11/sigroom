from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def workspace_data():
    unit = Unit.objects.create(code="UX29", name="หน่วย UX29")
    staff = User.objects.create_user(username="ux29-staff", unit=unit)
    room = Resource.objects.create(
        code="UX29-401",
        name="ห้องพัก UX29",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        status=Resource.Status.ACTIVE,
    )
    other_room = Resource.objects.create(
        code="UX29-999",
        name="ห้องพักนอกหลักสูตร",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        status=Resource.Status.ACTIVE,
    )
    start = timezone.localdate() + timedelta(days=7)
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตร UX29",
        slug="ux29",
        supervisor=staff,
        check_in_date=start,
        check_out_date=start + timedelta(days=4),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=False,
        beds_per_room=2,
    )
    cohort.rooms.add(room)
    return staff, room, other_room, cohort


def _workspace_url(**params):
    query = {"cohort": "ux29", **params}
    return reverse("bookings:lodging_workspace") + "?" + "&".join(f"{key}={value}" for key, value in query.items())


def test_free_beds_offer_direct_assignment_actions(client, workspace_data):
    staff, room, _, cohort = workspace_data
    client.force_login(staff)

    response = client.get(_workspace_url())
    html = response.content.decode()
    assert response.status_code == 200
    assert html.count("จัดคนลงเตียงนี้") == 2
    assert f"room={room.pk}&amp;bed=1#assign-heading" in html
    assert f"room={room.pk}&amp;bed=2#assign-heading" in html

    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=1,
        rank="ร.ต.",
        full_name="ผู้พักแล้ว",
        origin_unit="หน่วย UX29",
        phone="0812345678",
    )
    html = client.get(_workspace_url()).content.decode()
    assert html.count("จัดคนลงเตียงนี้") == 1
    assert f"room={room.pk}&amp;bed=1#assign-heading" not in html
    assert f"room={room.pk}&amp;bed=2#assign-heading" in html


def test_valid_free_bed_prefills_assignment_form(client, workspace_data):
    staff, room, _, _ = workspace_data
    client.force_login(staff)

    response = client.get(_workspace_url(room=room.pk, bed=2))
    assert response.status_code == 200
    form = response.context["form"]
    selected = response.context["selected_assignment"]
    assert form.initial["room_id"] == str(room.pk)
    assert form.initial["bed_number"] == "2"
    assert selected["room"].pk == room.pk
    assert selected["bed_number"] == 2
    html = response.content.decode()
    assert "เตียงที่เลือก" in html
    assert "ห้อง UX29-401 · เตียง 2" in html


def test_occupied_or_tampered_bed_is_not_prefilled(client, workspace_data):
    staff, room, other_room, cohort = workspace_data
    client.force_login(staff)
    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=1,
        rank="ร.ต.",
        full_name="ผู้พักแล้ว",
        origin_unit="หน่วย UX29",
        phone="0899999999",
    )

    occupied = client.get(_workspace_url(room=room.pk, bed=1))
    assert occupied.context["selected_assignment"] is None
    assert not occupied.context["form"].initial

    outsider = client.get(_workspace_url(room=other_room.pk, bed=1))
    assert outsider.context["selected_assignment"] is None
    assert not outsider.context["form"].initial

    out_of_range = client.get(_workspace_url(room=room.pk, bed=99))
    assert out_of_range.context["selected_assignment"] is None
    assert not out_of_range.context["form"].initial

    malformed = client.get(_workspace_url(room="not-a-room", bed="not-a-bed"))
    assert malformed.status_code == 200
    assert malformed.context["selected_assignment"] is None
    assert not malformed.context["form"].initial


def test_selection_is_presentation_only_and_post_still_revalidates(client, workspace_data):
    staff, room, _, cohort = workspace_data
    client.force_login(staff)
    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=2,
        rank="ร.ต.",
        full_name="ผู้พักก่อนหน้า",
        origin_unit="หน่วย UX29",
        phone="0822222222",
    )

    response = client.post(_workspace_url(room=room.pk, bed=2), {
        "room_id": str(room.pk),
        "bed_number": "2",
        "rank": "ร.ท.",
        "full_name": "ผู้พักใหม่",
        "origin_unit": "หน่วย UX29",
        "phone": "0833333333",
        "note": "",
    })
    assert response.status_code == 200
    assert "เตียงนี้มีเพื่อนร่วมรุ่นเพิ่งจองไปแล้ว" in response.content.decode()
    assert cohort.students.count() == 1

def test_released_cohort_does_not_offer_bed_first_actions(client, workspace_data):
    staff, room, _, cohort = workspace_data
    client.force_login(staff)
    cohort.allocation_status = CourseLodgingCohort.AllocationStatus.RELEASED
    cohort.save(update_fields=["allocation_status"])

    response = client.get(_workspace_url(room=room.pk, bed=1))
    assert response.status_code == 200
    assert response.context["selected_assignment"] is None
    assert response.context["assignment_open"] is False
    assert "จัดคนลงเตียงนี้" not in response.content.decode()

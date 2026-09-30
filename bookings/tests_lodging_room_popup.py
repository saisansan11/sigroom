from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import User
from resources.models import Resource
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging

pytestmark = pytest.mark.django_db


@pytest.fixture
def popup_room():
    return Resource.objects.create(code="DORM-423", name="ห้องทดสอบ", floor="4", capacity=2,
        resource_type=Resource.Type.ROOM, room_category=Resource.Category.LODGING)


@pytest.fixture
def popup_cohort(popup_room):
    owner = User.objects.create_user(username="popup-owner")
    cohort = CourseLodgingCohort.objects.create(title="หลักสูตรทดสอบ", slug="popup-course",
        supervisor=owner, beds_per_room=2, is_active=True,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        check_in_date=timezone.localdate(), check_out_date=timezone.localdate()+timedelta(days=3))
    cohort.rooms.add(popup_room)
    return cohort


def test_missing_or_non_lodging_plan_room_is_not_bookable(client):
    for number in (423, 408, 101, 999):
        response = client.get(f"/lodging/rooms/{number}/")
        assert response.json() == {"room": None}
        assert response.headers["Cache-Control"] == "no-store"


def test_room_uses_real_id_and_no_context_free_availability(client, popup_room):
    data = client.get("/lodging/rooms/423/").json()["room"]
    assert data["id"] == str(popup_room.pk)
    assert data["cohorts"] == []
    assert data["request_url"].endswith(f"?room_id={popup_room.pk}")
    assert "free" not in data


def test_partial_full_and_closed_cohort_counts_do_not_expose_people(client, popup_room, popup_cohort):
    for bed in (1, 2):
        CourseStudentLodging.objects.create(cohort=popup_cohort, room=popup_room, bed_number=bed,
            rank="ร.ต.", full_name="PRIVATE NAME", origin_unit="PRIVATE UNIT", phone=f"081234567{bed}")
        response = client.get("/lodging/rooms/423/")
        data = response.json()["room"]["cohorts"][0]
        assert (data["used"], data["free"], data["total"]) == (bed, 2-bed, 2)
        assert f"room_id={popup_room.pk}" in data["url"]
        assert "PRIVATE" not in response.content.decode()
        assert "081234567" not in response.content.decode()
    popup_cohort.is_active = False
    popup_cohort.save()
    assert client.get("/lodging/rooms/423/").json()["room"]["cohorts"] == []


def test_inactive_room_has_no_booking_links(client, popup_room):
    popup_room.status = Resource.Status.OUT_OF_SERVICE
    popup_room.save()
    data = client.get("/lodging/rooms/423/").json()["room"]
    assert data["active"] is False
    assert data["request_url"] is None
    assert data["cohorts"] == []


def test_ambiguous_code_or_wrong_floor_fails_closed(client, popup_room):
    other = Resource.objects.create(code="423", name="another", room_category=Resource.Category.LODGING)
    assert client.get("/lodging/rooms/423/").json()["room"] is None
    other.delete()
    popup_room.floor = "5"
    popup_room.save()
    assert client.get("/lodging/rooms/423/").json()["room"] is None


def test_selected_room_is_preserved_in_portal(client, popup_room, popup_cohort):
    response = client.get(f"/lodging/c/{popup_cohort.slug}/", {"room_id": popup_room.pk})
    assert response.context["selected_room"]["room"] == popup_room
    assert response.context["rooms_data"][0]["room"] == popup_room
    assert 'data-selected="true"' in response.content.decode()
    response = client.get(f"/lodging/c/{popup_cohort.slug}/", {"room_id": "999999"})
    assert response.context["selected_room"] is None
    assert "ไม่อยู่ในหลักสูตร" in response.content.decode()


@pytest.mark.parametrize("value", ["bad", "-1", "9"*100])
def test_invalid_general_prefill_recovers(client, value):
    response = client.get("/lodging/request/", {"room_id": value})
    assert response.status_code == 200
    assert "room" not in response.context["form"].initial


def test_general_prefill_uses_model_choice_and_never_trusts_query_on_post(client, popup_room):
    response = client.get("/lodging/request/", {"room_id": popup_room.pk})
    assert response.context["form"].initial["room"] == popup_room.pk
    response = client.post(f"/lodging/request/?room_id={popup_room.pk}", {"room": "999999"})
    assert "room" in response.context["form"].errors


def test_read_endpoint_rejects_post(client, popup_room):
    assert client.post("/lodging/rooms/423/").status_code == 405

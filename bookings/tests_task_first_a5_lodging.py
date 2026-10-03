from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_about_data import FLOOR4_LODGING_ROOMS, FLOOR5_LODGING_ROOMS, TOTAL_ROOMS
from bookings.lodging_models import CourseLodgingCohort
from bookings.lodging_services import available_public_lodging_rooms, request_general_lodging
from bookings.models import Booking
from resources.models import Blackout, Resource, ResourceRule

pytestmark = pytest.mark.django_db

PASSWORD = "Password-2569"


def _room(code, capacity=2):
    room = Resource.objects.create(
        code=code,
        name=f"ห้อง {code}",
        building="อาคารที่พักทดสอบ",
        floor="4",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=capacity,
        status=Resource.Status.ACTIVE,
    )
    ResourceRule.objects.create(resource=room, approval_policy=ResourceRule.ApprovalPolicy.REQUIRED)
    return room


def _authoritative_rooms():
    rooms = []
    for number in FLOOR4_LODGING_ROOMS + FLOOR5_LODGING_ROOMS:
        rooms.append(
            Resource(
                code=str(number),
                name=f"ห้อง {number}",
                building="อาคารที่พักทดสอบ",
                floor=str(number)[0],
                resource_type=Resource.Type.ROOM,
                room_category=Resource.Category.LODGING,
                capacity=2 if number in FLOOR4_LODGING_ROOMS else 4,
                status=Resource.Status.ACTIVE,
            )
        )
    Resource.objects.bulk_create(rooms)
    created = list(Resource.objects.filter(code__in=[str(n) for n in FLOOR4_LODGING_ROOMS + FLOOR5_LODGING_ROOMS]))
    ResourceRule.objects.bulk_create(
        [
            ResourceRule(resource=room, approval_policy=ResourceRule.ApprovalPolicy.REQUIRED)
            for room in created
        ]
    )
    assert len(created) == TOTAL_ROOMS
    return created


def _user(username="a5-staff"):
    unit = Unit.objects.create(code=f"U-{username[:8]}", name=f"หน่วย {username}")
    return User.objects.create_user(
        username=username,
        email=f"{username}@signalschool.ac.th",
        password=PASSWORD,
        unit=unit,
    )


def _cohort(*, slug, supervisor, room, offset=1):
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title=f"หลักสูตร {slug}",
        slug=slug,
        supervisor=supervisor,
        unit=supervisor.unit,
        check_in_date=today + timedelta(days=offset),
        check_out_date=today + timedelta(days=offset + 2),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
        beds_per_room=2,
    )
    cohort.rooms.add(room)
    return cohort


def test_lodging_start_is_public_and_has_two_paths(client):
    response = client.get(reverse("bookings:lodging_start"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "นักเรียนหลักสูตร" in html
    assert "บุคคลทั่วไป" in html
    assert reverse("bookings:lodging_index") in html
    assert reverse("bookings:lodging_general_request") in html


def test_lodging_index_single_open_cohort_redirects_to_portal(client):
    staff = _user("a5-supervisor")
    room = _room("A5-C401")
    cohort = _cohort(slug="a5-one", supervisor=staff, room=room)
    response = client.get(reverse("bookings:lodging_index"))
    assert response.status_code == 302
    assert response.url == reverse("bookings:lodging_portal", args=[cohort.slug])


def test_lodging_index_two_open_cohorts_lists_them(client):
    staff = _user("a5-supervisor2")
    room1 = _room("A5-C402")
    room2 = _room("A5-C403")
    _cohort(slug="a5-two-a", supervisor=staff, room=room1)
    _cohort(slug="a5-two-b", supervisor=staff, room=room2, offset=5)
    response = client.get(reverse("bookings:lodging_index"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "หลักสูตร a5-two-a" in html
    assert "หลักสูตร a5-two-b" in html


def test_lodging_index_no_open_cohort_points_back_to_start(client):
    response = client.get(reverse("bookings:lodging_index"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "ยังไม่มีรอบที่เปิดจอง" in html
    assert reverse("bookings:lodging_start") in html


def test_lodging_manager_does_not_auto_redirect_single_cohort(client):
    manager = _user("a5-manager")
    manager.user_permissions.add(Permission.objects.get(codename="add_courselodgingcohort"))
    room = _room("A5-C404")
    _cohort(slug="a5-manager-one", supervisor=manager, room=room)
    client.force_login(manager)
    response = client.get(reverse("bookings:lodging_index"))
    assert response.status_code == 200
    assert "จัดการที่พัก" in response.content.decode("utf-8")


def test_available_rooms_excludes_overlapping_pending_request():
    room1 = _room("A5-P401", capacity=2)
    room2 = _room("A5-P402", capacity=2)
    check_in = timezone.localdate() + timedelta(days=2)
    check_out = check_in + timedelta(days=2)
    booking = request_general_lodging(
        room=room1,
        check_in=check_in,
        check_out=check_out,
        attendees=1,
        guest_name="ผู้ทดสอบ",
        phone="0811111111",
    )
    assert booking.request_status == Booking.RequestStatus.PENDING

    rooms = available_public_lodging_rooms(check_in=check_in, check_out=check_out, attendees=1)
    assert room1 not in rooms
    assert room2 in rooms


def test_checkout_at_noon_does_not_block_new_checkin_at_1400():
    room = _room("A5-P403", capacity=2)
    first_in = timezone.localdate() + timedelta(days=2)
    handoff_day = first_in + timedelta(days=2)
    request_general_lodging(
        room=room,
        check_in=first_in,
        check_out=handoff_day,
        attendees=1,
        guest_name="ผู้พักชุดแรก",
        phone="0822222222",
    )
    rooms = available_public_lodging_rooms(
        check_in=handoff_day,
        check_out=handoff_day + timedelta(days=1),
        attendees=1,
    )
    assert room in rooms


def test_available_rooms_sort_capacity_fit_then_unspecified_then_undersized():
    exact = _room("A5-S201", capacity=2)
    bigger = _room("A5-S401", capacity=4)
    unspecified = _room("A5-S000", capacity=0)
    too_small = _room("A5-S101", capacity=1)
    check_in = timezone.localdate() + timedelta(days=2)
    check_out = check_in + timedelta(days=1)
    rooms = available_public_lodging_rooms(check_in=check_in, check_out=check_out, attendees=2)
    selected = [room for room in rooms if room in {exact, bigger, unspecified, too_small}]
    assert selected == [exact, bigger, unspecified, too_small]


def test_post_general_request_persists_attendees(client):
    room = _room("A5-F401", capacity=2)
    check_in = timezone.localdate() + timedelta(days=2)
    check_out = check_in + timedelta(days=2)
    response = client.post(
        reverse("bookings:lodging_general_request"),
        {
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
            "attendees": "2",
            "guest_name": "ผู้ทดสอบสองคน",
            "phone": "0833333333",
            "room": str(room.pk),
            "note": "",
        },
    )
    assert response.status_code == 302
    booking = Booking.objects.get(room=room)
    assert booking.attendees == 2


def test_general_request_rechecks_room_and_does_not_create_second_overlap(client):
    room = _room("A5-F402", capacity=2)
    check_in = timezone.localdate() + timedelta(days=2)
    check_out = check_in + timedelta(days=1)
    request_general_lodging(
        room=room,
        check_in=check_in,
        check_out=check_out,
        attendees=1,
        guest_name="จองก่อน",
        phone="0844444444",
    )
    response = client.post(
        reverse("bookings:lodging_general_request"),
        {
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
            "attendees": "1",
            "guest_name": "จองทีหลัง",
            "phone": "0855555555",
            "room": str(room.pk),
            "note": "",
        },
    )
    assert response.status_code == 200
    assert Booking.objects.filter(room=room).count() == 1


def test_room_partial_bounds_scan_and_does_not_leak_guest_name(client):
    room = _room("A5-F403", capacity=2)
    check_in = timezone.localdate() + timedelta(days=2)
    check_out = check_in + timedelta(days=1)
    request_general_lodging(
        room=room,
        check_in=check_in,
        check_out=check_out,
        attendees=1,
        guest_name="ชื่อที่ห้ามรั่ว SECRET-GUEST",
        phone="0866666666",
    )
    response = client.get(
        reverse("bookings:lodging_general_request_rooms"),
        {"check_in": check_in.isoformat(), "check_out": check_out.isoformat(), "attendees": 1},
    )
    assert response.status_code == 200
    assert "SECRET-GUEST" not in response.content.decode("utf-8")

    past = timezone.localdate() - timedelta(days=1)
    invalid = client.get(
        reverse("bookings:lodging_general_request_rooms"),
        {"check_in": past.isoformat(), "check_out": timezone.localdate().isoformat(), "attendees": 1},
    )
    assert invalid.status_code == 400

    too_far = timezone.localdate() + timedelta(days=61)
    invalid = client.get(
        reverse("bookings:lodging_general_request_rooms"),
        {"check_in": too_far.isoformat(), "check_out": (too_far + timedelta(days=1)).isoformat(), "attendees": 1},
    )
    assert invalid.status_code == 400


def test_room_id_is_preselected_when_available(client):
    room = _room("A5-F404", capacity=2)
    check_in = timezone.localdate() + timedelta(days=2)
    check_out = check_in + timedelta(days=1)
    response = client.get(
        reverse("bookings:lodging_general_request"),
        {"check_in": check_in.isoformat(), "check_out": check_out.isoformat(), "attendees": 1, "room_id": room.pk},
    )
    assert response.status_code == 200
    assert str(response.context["form"].initial["room"]) == str(room.pk)


def test_attendee_plus_button_has_server_side_fallback(client):
    room = _room("A5-F405", capacity=3)
    check_in = timezone.localdate() + timedelta(days=2)
    check_out = check_in + timedelta(days=1)
    response = client.get(
        reverse("bookings:lodging_general_request"),
        {
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
            "attendees": "1",
            "attendees_delta": "1",
        },
    )
    assert response.status_code == 200
    assert str(response.context["form"].initial["attendees"]) == "2"
    assert room in list(response.context["form"].fields["room"].queryset)


@pytest.mark.parametrize(
    "route_name",
    ["bookings:lodging_general_request_rooms", "bookings:lodging_general_request"],
)
@pytest.mark.parametrize("all_blocked", [False, True], ids=["available", "full"])
def test_public_lodging_search_query_budget_87_rooms(
    client, django_assert_max_num_queries, route_name, all_blocked
):
    _authoritative_rooms()
    check_in = timezone.localdate() + timedelta(days=20)
    check_out = check_in + timedelta(days=2)
    if all_blocked:
        zone = timezone.get_current_timezone()
        Blackout.objects.create(
            title="ปิดทดสอบ query budget",
            start_at=timezone.make_aware(datetime.combine(check_in - timedelta(days=7), time.min), zone),
            end_at=timezone.make_aware(datetime.combine(check_out + timedelta(days=8), time.min), zone),
            scope=Blackout.Scope.ALL,
        )

    params = {
        "check_in": check_in.isoformat(),
        "check_out": check_out.isoformat(),
        "attendees": "1",
    }
    with django_assert_max_num_queries(25):
        response = client.get(reverse(route_name), params)

    assert response.status_code == 200
    expected_count = 0 if all_blocked else TOTAL_ROOMS
    assert response.context["available_room_count"] == expected_count

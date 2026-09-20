from datetime import timedelta
import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, Unit
from resources.models import Resource
from bookings.models import Booking, CourseLodgingCohort
from bookings.lodging_services import assign_lodging_bed, request_general_lodging

pytestmark = pytest.mark.django_db


@pytest.fixture
def data():
    unit = Unit.objects.create(code="UX28", name="หน่วยทดสอบ")
    staff = User.objects.create_user(username="ux28", unit=unit)
    room = Resource.objects.create(code="UX28-401", name="ห้องพัก", resource_type="room", room_category="lodging")
    start = timezone.localdate() + timedelta(days=4)
    cohort = CourseLodgingCohort.objects.create(title="หลักสูตรทดสอบ", slug="ux28",
        supervisor=staff, check_in_date=start, check_out_date=start + timedelta(days=5),
        allocation_status="allocated", is_active=False, beds_per_room=2)
    cohort.rooms.add(room)
    return staff, room, cohort


def assign(data, **kwargs):
    staff, room, cohort = data
    values = dict(cohort=cohort, room_id=room.pk, bed_number=1, rank="ร.ต.",
                  full_name="ผู้พักทดสอบ", origin_unit="หน่วยทดสอบ", phone="0812345678", actor=staff)
    values.update(kwargs)
    return assign_lodging_bed(**values)


def test_staff_can_assign_while_public_closed(data):
    assert assign(data).bed_number == 1


def test_public_cannot_assign_closed_or_stale_cohort(data):
    with pytest.raises(ValidationError):
        assign(data, actor=None)
    data[2].is_active = True  # stale caller must not bypass the locked DB state
    with pytest.raises(ValidationError):
        assign(data, actor=None)


def test_staff_cannot_assign_released(data):
    CourseLodgingCohort.objects.filter(pk=data[2].pk).update(allocation_status="released")
    with pytest.raises(ValidationError):
        assign(data)


def test_permission_and_duplicate_protection(data):
    outsider = User.objects.create_user(username="outsider", email="outsider@example.test")
    with pytest.raises(PermissionDenied):
        assign(data, actor=outsider)
    assign(data)
    with pytest.raises(ValidationError):
        assign(data, phone="0899999999")
    with pytest.raises(ValidationError):
        assign(data, bed_number=2, phone="081-234-5678")


def test_workspace_privacy_and_validation(client, data):
    url = reverse("bookings:lodging_workspace") + "?cohort=ux28"
    assert client.get(url).status_code == 302
    assign(data)
    client.force_login(data[0])
    response = client.get(url)
    assert response.status_code == 200
    assert "ผู้พักทดสอบ" in response.content.decode()
    assert "no-store" in response.headers["Cache-Control"]
    response = client.post(url, {"full_name": "คงข้อมูลที่กรอก"})
    assert "คงข้อมูลที่กรอก" in response.content.decode()


def test_workspace_can_open_public_self_booking_after_allocation(client, data):
    staff, room, cohort = data
    client.force_login(staff)
    response = client.post(reverse("bookings:lodging_workspace") + "?cohort=ux28", {
        "action": "allocation", "rooms": [str(room.pk)], "is_active": "on",
    })
    assert response.status_code == 302
    cohort.refresh_from_db()
    assert cohort.is_active is True
    assert list(cohort.rooms.values_list("pk", flat=True)) == [room.pk]


def test_general_request_pending_and_conflict(data):
    staff, room, cohort = data
    with pytest.raises(ValidationError):
        request_general_lodging(actor=staff, room=room, check_in=cohort.check_in_date,
            check_out=cohort.check_out_date, phone="0812345678")
    start = cohort.check_out_date + timedelta(days=3)
    booking = request_general_lodging(actor=staff, room=room, check_in=start,
        check_out=start + timedelta(days=4), phone="0812345678")
    assert booking.request_status == Booking.RequestStatus.PENDING
    assert booking.holds.filter(released_at__isnull=True).exists()


def test_public_entry_routes(client):
    response = client.get(reverse("bookings:lodging_about"))
    assert reverse("bookings:lodging_general_request") in response.content.decode()
    assert reverse("bookings:lodging_index") in response.content.decode()

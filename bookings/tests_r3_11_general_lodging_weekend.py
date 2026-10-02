from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from bookings.models import Booking
from resources.models import Resource


pytestmark = pytest.mark.django_db


def _next_weekday(target_weekday: int):
    today = timezone.localdate()
    days_ahead = (target_weekday - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return today + timedelta(days=days_ahead)


@pytest.fixture
def public_lodging_room():
    return Resource.objects.create(
        code="R3-11-PUBLIC",
        name="ห้องพักทดสอบวันหยุด R3-11",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=2,
        status=Resource.Status.ACTIVE,
    )


@pytest.mark.parametrize(
    ("arrival_weekday", "label", "phone"),
    [
        (5, "วันเสาร์", "081-234-5611"),
        (6, "วันอาทิตย์", "081-234-5612"),
    ],
)
def test_public_general_lodging_accepts_weekend_arrival(
    client,
    public_lodging_room,
    arrival_weekday,
    label,
    phone,
):
    """R3-11: ห้องพักคนทั่วไปต้องยื่นคำขอเข้าเสาร์หรืออาทิตย์ได้."""
    check_in = _next_weekday(arrival_weekday)
    check_out = check_in + timedelta(days=1)

    response = client.post(
        reverse("bookings:lodging_general_request"),
        {
            "guest_name": f"ผู้เข้าพักทดสอบ {label}",
            "room": str(public_lodging_room.pk),
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
            "phone": phone,
            "note": f"ทดสอบเข้าพัก{label}",
        },
    )

    assert response.status_code == 302
    booking = Booking.objects.get(title="คำขอเข้าพักทั่วไป")
    assert timezone.localtime(booking.start_at).date() == check_in
    assert timezone.localtime(booking.end_at).date() == check_out
    assert timezone.localtime(booking.start_at).date().weekday() == arrival_weekday
    assert booking.request_status == Booking.RequestStatus.PENDING

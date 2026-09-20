from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from approvals.services import approve_booking, reject_booking
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging, PublicLodgingAccess
from bookings.lodging_services import assign_lodging_bed, cohort_self_booking_status
from bookings.models import Booking
from resources.models import Resource, ResourceApprover

pytestmark = pytest.mark.django_db


@pytest.fixture
def lodging_room():
    return Resource.objects.create(
        code="PB-101",
        name="ห้องพักทดสอบ Phase B",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
    )


@pytest.fixture
def approver(lodging_room):
    unit = Unit.objects.create(code="PBSTAFF", name="เจ้าหน้าที่ Phase B")
    user = User.objects.create_user(
        username="phaseb-approver",
        email="phaseb-approver@signalschool.ac.th",
        password="test-pass",
        unit=unit,
    )
    ResourceApprover.objects.create(resource=lodging_room, user=user, is_primary=True)
    return user


def _public_request_payload(room, *, offset_days=5):
    check_in = timezone.localdate() + timedelta(days=offset_days)
    return {
        "guest_name": "สมชาย ผู้เข้าพัก",
        "room": str(room.pk),
        "check_in": check_in.isoformat(),
        "check_out": (check_in + timedelta(days=2)).isoformat(),
        "phone": "081-234-5678",
        "note": "มาถึงช่วงเย็น",
    }


def _cohort(room, *, slug, open_at, close_at, active=True):
    unit = Unit.objects.create(code=f"U-{slug}"[:20], name=f"หน่วย {slug}")
    supervisor = User.objects.create_user(
        username=f"sup-{slug}",
        email=f"sup-{slug}@signalschool.ac.th",
        password="test-pass",
        unit=unit,
    )
    stay = timezone.localdate() + timedelta(days=10)
    cohort = CourseLodgingCohort.objects.create(
        title=f"หลักสูตร {slug}",
        slug=slug,
        supervisor=supervisor,
        unit=unit,
        check_in_date=stay,
        check_out_date=stay + timedelta(days=5),
        beds_per_room=4,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=active,
        booking_open_at=open_at,
        booking_close_at=close_at,
    )
    cohort.rooms.add(room)
    return cohort


def test_anonymous_guest_can_submit_pending_request_and_get_private_status_link(client, lodging_room):
    response = client.post(reverse("bookings:lodging_general_request"), _public_request_payload(lodging_room))
    assert response.status_code == 302

    booking = Booking.objects.get(title="คำขอเข้าพักทั่วไป")
    assert booking.request_status == Booking.RequestStatus.PENDING
    assert booking.responsible_name == "สมชาย ผู้เข้าพัก"
    assert booking.requester.username == "public-lodging"
    assert booking.requester.is_active is False
    assert booking.requester.phone == "SYSTEM"
    assert booking.holds.filter(released_at__isnull=True).exists()

    access = PublicLodgingAccess.objects.get(booking=booking)
    assert response.url == reverse("bookings:lodging_general_request_status", args=[access.pk])

    status = client.get(response.url)
    html = status.content.decode("utf-8")
    assert status.status_code == 200
    assert "รออนุมัติ" in html
    assert "สมชาย ผู้เข้าพัก" in html
    assert "no-store" in status.headers["Cache-Control"]
    assert status.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_public_request_status_follows_approval_and_rejection(client, lodging_room, approver):
    client.post(reverse("bookings:lodging_general_request"), _public_request_payload(lodging_room))
    booking = Booking.objects.get(title="คำขอเข้าพักทั่วไป")
    access = booking.public_lodging_access

    approve_booking(booking, approver)
    approved = client.get(reverse("bookings:lodging_general_request_status", args=[access.pk]))
    assert "อนุมัติ" in approved.content.decode("utf-8")

    payload = _public_request_payload(lodging_room, offset_days=12)
    # First approved request holds another time range, so a non-overlapping request is valid.
    client.post(reverse("bookings:lodging_general_request"), payload)
    second = Booking.objects.exclude(pk=booking.pk).get(title="คำขอเข้าพักทั่วไป")
    reject_booking(second, approver, "ห้องปิดปรับปรุง")
    rejected = client.get(reverse("bookings:lodging_general_request_status", args=[second.public_lodging_access.pk]))
    body = rejected.content.decode("utf-8")
    assert "ปฏิเสธ" in body
    assert "ห้องปิดปรับปรุง" in body
    assert not second.holds.filter(released_at__isnull=True).exists()


def test_unknown_public_status_token_is_not_discoverable(client):
    import uuid

    response = client.get(reverse("bookings:lodging_general_request_status", args=[uuid.uuid4()]))
    assert response.status_code == 404


def test_course_booking_window_blocks_before_open_even_on_direct_post(client, lodging_room):
    now = timezone.now()
    cohort = _cohort(
        lodging_room,
        slug="future-window",
        open_at=now + timedelta(hours=2),
        close_at=now + timedelta(days=2),
    )
    assert cohort_self_booking_status(cohort, now)[0] == "not_open"
    portal = client.get(reverse("bookings:lodging_portal", args=[cohort.slug]))
    assert portal.status_code == 200
    assert "ยังไม่เปิดรับจอง" in portal.content.decode("utf-8")
    assert "no-store" in portal.headers["Cache-Control"]

    response = client.post(
        reverse("bookings:lodging_book_bed", args=[cohort.slug]),
        {
            "room_id": str(lodging_room.pk),
            "bed_number": "1",
            "rank": "ร.ต.",
            "full_name": "ผู้พยายามข้ามเวลา",
            "origin_unit": "หน่วยทดสอบ",
            "phone": "0821112222",
        },
    )
    assert response.status_code == 302
    assert CourseStudentLodging.objects.filter(cohort=cohort).count() == 0


def test_course_booking_window_allows_open_window_and_blocks_after_close(lodging_room):
    now = timezone.now()
    cohort = _cohort(
        lodging_room,
        slug="open-window",
        open_at=now - timedelta(hours=1),
        close_at=now + timedelta(hours=1),
    )
    assert cohort_self_booking_status(cohort, now)[0] == "open"
    student = assign_lodging_bed(
        cohort=cohort,
        room_id=lodging_room.pk,
        bed_number=1,
        rank="ร.ต.",
        full_name="นักเรียนในช่วงเปิด",
        origin_unit="หน่วยทดสอบ",
        phone="0831112222",
        actor=None,
    )
    assert student.pk

    CourseLodgingCohort.objects.filter(pk=cohort.pk).update(booking_close_at=now - timedelta(minutes=1))
    cohort.refresh_from_db()
    assert cohort_self_booking_status(cohort, now)[0] == "closed"
    with pytest.raises(ValidationError, match="หมดเวลารับจอง"):
        assign_lodging_bed(
            cohort=cohort,
            room_id=lodging_room.pk,
            bed_number=2,
            rank="ร.ต.",
            full_name="นักเรียนหลังปิด",
            origin_unit="หน่วยทดสอบ",
            phone="0841112222",
            actor=None,
        )


def test_legacy_active_cohort_without_window_remains_compatible(lodging_room):
    cohort = _cohort(lodging_room, slug="legacy", open_at=None, close_at=None)
    assert cohort_self_booking_status(cohort)[0] == "open"

"""UI-3 Booking Flow semantic contracts and presentation verification."""
from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from resources.models import Resource, ResourceApprover, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def ui3_setup():
    hq = Unit.objects.create(code="UI3-HQ", name="กองบัญชาการ UI3")
    comm = Unit.objects.create(code="UI3-COMM", name="แผนกสื่อสาร UI3", parent=hq)
    user = User.objects.create_user(
        username="ui3_requester",
        email="ui3_requester@signalschool.ac.th",
        password="Password-2569",
        unit=comm,
        rank="ร.อ.",
        first_name="สมชาย",
        last_name="ใจดี",
        phone="081-999-8888",
    )
    approver = User.objects.create_user(
        username="ui3_approver",
        email="ui3_approver@signalschool.ac.th",
        password="Password-2569",
        unit=hq,
        rank="พ.ท.",
        first_name="ประสิทธิ์",
        last_name="รักชาติ",
        phone="081-777-6666",
    )

    auto_room = Resource.objects.create(
        code="UI3-AUTO",
        name="ห้องบรรยายอัตโนมัติ",
        capacity=40,
        building="อาคาร 1",
        floor="2",
    )
    ResourceRule.objects.create(
        resource=auto_room,
        approval_policy=ResourceRule.ApprovalPolicy.AUTO,
        service_start=time(7, 0),
        service_end=time(21, 0),
    )

    review_room = Resource.objects.create(
        code="UI3-REVIEW",
        name="ห้องประชุมใหญ่ต้องอนุมัติ",
        capacity=80,
        building="อาคาร 2",
        floor="3",
    )
    ResourceRule.objects.create(
        resource=review_room,
        approval_policy=ResourceRule.ApprovalPolicy.REQUIRED,
        service_start=time(7, 0),
        service_end=time(21, 0),
    )
    ResourceApprover.objects.create(resource=review_room, user=approver, is_primary=True)

    mic = Resource.objects.create(
        code="UI3-MIC",
        name="ไมค์ไร้สาย",
        resource_type=Resource.Type.EQUIPMENT,
        status=Resource.Status.ACTIVE,
    )

    return {
        "user": user,
        "approver": approver,
        "auto_room": auto_room,
        "review_room": review_room,
        "mic": mic,
    }


def test_booking_stepper_rendered_on_search_form_and_detail(client, ui3_setup):
    user = ui3_setup["user"]
    auto_room = ui33_room = ui3_setup["auto_room"]
    client.force_login(user)

    # Step 1 Search
    res_search = client.get(reverse("bookings:book_search"))
    assert res_search.status_code == 200
    content_search = res_search.content.decode()
    assert "booking-stepper" in content_search
    assert 'aria-label="ขั้นตอนการจองห้อง"' in content_search
    assert 'ขั้นตอนที่ 1 จาก 5' in content_search
    assert "ค้นหาห้องว่าง" in content_search

    # Step 3 Form
    res_form = client.get(
        reverse("bookings:book_form", args=[auto_room.code]),
        {"search": "1", "date": (timezone.localdate() + timedelta(days=2)).isoformat(), "start": "09:00", "end": "10:00"},
    )
    assert res_form.status_code == 200
    content_form = res_form.content.decode()
    assert "booking-stepper" in content_form
    assert "ขั้นตอนที่ 3 จาก 5" in content_form
    assert "สรุปการจอง" in content_form
    assert "ตรวจสอบข้อมูลก่อนส่ง" in content_form
    assert "ยืนยันและส่งคำขอ" in content_form
    assert 'class="booking-stepper-compact"' in content_form
    assert 'class="booking-stepper-compact" aria-hidden="true"' not in content_form
    assert "ผู้เข้าร่วมภายนอกหรือเงื่อนไขเพิ่มเติมอาจทำให้ต้องผ่านผู้อนุมัติ" in content_form

    # Step 5 Detail
    start_dt = timezone.now() + timedelta(days=2)
    end_dt = start_dt + timedelta(hours=1)
    booking = Booking.objects.create(
        room=auto_room,
        requester=user,
        unit=user.unit,
        responsible_name=user.display_name,
        responsible_phone=user.phone,
        title="ทดสอบ UI3",
        start_at=start_dt,
        end_at=end_dt,
        request_status=Booking.RequestStatus.APPROVED,
    )
    res_detail = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert res_detail.status_code == 200
    content_detail = res_detail.content.decode()
    assert "booking-stepper" in content_detail
    assert "ขั้นตอนที่ 5 จาก 5" in content_detail
    assert "booking-status-hero" in content_detail
    assert "อนุมัติแล้ว" in content_detail


def test_book_search_equipment_progressive_disclosure(client, ui3_setup):
    user = ui3_setup["user"]
    client.force_login(user)
    res = client.get(reverse("bookings:book_search"))
    assert res.status_code == 200
    content = res.content.decode()
    assert 'class="search-equipment-details"' in content or "search-equipment-details" in content
    assert "ค้นหาห้องว่าง" in content


def test_room_result_cta_and_approval_label(client, ui3_setup):
    setup = ui3_setup
    user = setup["user"]
    client.force_login(user)
    date_str = (timezone.localdate() + timedelta(days=3)).strftime("%d/%m/") + str(timezone.localdate().year + 543)
    res = client.get(
        reverse("bookings:book_search"),
        {"search": "1", "date": date_str, "start": "09:00", "end": "10:00"},
        headers={"HX-Request": "true"},
    )
    assert res.status_code == 200
    content = res.content.decode()
    assert "จองห้องนี้" in content
    assert "policy-badge" in content
    assert "UI3-AUTO" in content
    assert "UI3-REVIEW" in content


def test_guest_redirected_from_booking(client):
    res = client.get(reverse("bookings:book_search"))
    assert res.status_code == 302
    assert "/login" in res.url


def test_approver_actions_preserved_on_pending(client, ui3_setup):
    approver = ui3_setup["approver"]
    user = ui3_setup["user"]
    review_room = ui3_setup["review_room"]

    start_dt = timezone.now() + timedelta(days=2)
    end_dt = start_dt + timedelta(hours=1)
    booking = Booking.objects.create(
        room=review_room,
        requester=user,
        unit=user.unit,
        responsible_name=user.display_name,
        responsible_phone=user.phone,
        title="ขอใช้ห้องประชุมใหญ่",
        start_at=start_dt,
        end_at=end_dt,
        request_status=Booking.RequestStatus.PENDING,
    )

    client.force_login(approver)
    res = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert res.status_code == 200
    content = res.content.decode()
    assert "อนุมัติคำขอ" in content
    assert "ปฏิเสธ" in content
    assert "booking-status-hero" in content
    assert "ส่งคำขอแล้ว · รอผู้อนุมัติ" in content

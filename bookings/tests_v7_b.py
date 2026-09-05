"""เทสงาน B (แผน V7): หมวดห้องสอนออนไลน์ + ลิงก์ประชุม + สิทธิ์เห็นลิงก์ 4 มุมมอง"""
from datetime import datetime, time, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.forms import BookingForm
from bookings.models import Booking
from bookings.services import (
    POST_SUBMIT_EDITABLE_FIELDS,
    can_view_details,
    can_view_online_link,
    submit_booking,
)
from notifications.models import Notification
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db

MEET_URL = "https://meet.google.com/abc-defg-hij"


def _aware(day=10, hour=10, minute=0):
    return timezone.make_aware(
        datetime(2026, 9, day, hour, minute), timezone.get_current_timezone()
    )


@pytest.fixture
def online_setup():
    unit = Unit.objects.create(code="V7B-EDU", name="กองการศึกษา (ทดสอบ)")
    other_unit = Unit.objects.create(code="V7B-OTHER", name="หน่วยอื่น")
    requester = User.objects.create_user(
        username="v7b-req", email="v7b-req@signalschool.ac.th",
        password="Password-2569", unit=unit,
    )
    same_unit_user = User.objects.create_user(
        username="v7b-same", email="v7b-same@signalschool.ac.th",
        password="Password-2569", unit=unit,
    )
    other_unit_user = User.objects.create_user(
        username="v7b-other", email="v7b-other@signalschool.ac.th",
        password="Password-2569", unit=other_unit,
    )
    custodian = User.objects.create_user(
        username="v7b-staff", email="v7b-staff@signalschool.ac.th",
        password="Password-2569", unit=other_unit,
    )

    def make_room(code, category):
        room = Resource.objects.create(
            code=code, name=f"ห้อง {code}", resource_type=Resource.Type.ROOM,
            room_category=category, building="อาคาร บก.กศ.", capacity=5, owner_unit=unit,
        )
        ResourceRule.objects.create(resource=room, service_start=time(7), service_end=time(21))
        return room

    online_room = make_room("V7B-ON1", Resource.Category.ONLINE)
    online_room.custodians.add(custodian)
    classroom = make_room("V7B-C1", Resource.Category.CLASSROOM)

    booking = Booking.objects.create(
        room=online_room, requester=requester, unit=unit,
        responsible_name="ผู้ทดสอบ", responsible_phone="0812345678",
        title="สอนออนไลน์วิชาทดสอบ",
        start_at=_aware(hour=10), end_at=_aware(hour=11),
        online_meeting_url=MEET_URL,
    )
    submit_booking(booking)
    return requester, same_unit_user, other_unit_user, custodian, online_room, classroom, booking


def test_can_view_online_link_is_stricter_than_can_view_details(online_setup):
    requester, same_unit_user, other_unit_user, custodian, _, _, booking = online_setup

    assert can_view_online_link(requester, booking) is True
    assert can_view_online_link(custodian, booking) is True  # เจ้าหน้าที่ดูแลห้อง

    # หัวใจของงาน B: คนหน่วยเดียวกันเห็นรายละเอียดได้ แต่ต้องไม่เห็นลิงก์
    assert can_view_details(same_unit_user, booking) is True
    assert can_view_online_link(same_unit_user, booking) is False

    assert can_view_online_link(other_unit_user, booking) is False

    superuser = User.objects.create_superuser(
        username="v7b-su", email="v7b-su@signalschool.ac.th", password="Password-2569"
    )
    assert can_view_online_link(superuser, booking) is True


def test_can_view_online_link_rejects_anonymous(online_setup):
    from django.contrib.auth.models import AnonymousUser

    *_, booking = online_setup
    assert can_view_online_link(AnonymousUser(), booking) is False


def test_detail_page_shows_link_to_requester_but_not_same_unit(client, online_setup):
    requester, same_unit_user, *_, booking = online_setup
    url = reverse("bookings:booking_detail", args=[booking.id])

    client.force_login(requester)
    assert MEET_URL in client.get(url).content.decode()

    client.force_login(same_unit_user)
    resp = client.get(url)
    content = resp.content.decode()
    assert resp.status_code == 200
    assert "สอนออนไลน์วิชาทดสอบ" in content  # เห็นรายละเอียดตาม can_view_details เดิม
    assert MEET_URL not in content           # แต่ไม่เห็นลิงก์


def test_masked_page_for_other_unit_has_no_link(client, online_setup):
    _, _, other_unit_user, *_ , booking = online_setup
    client.force_login(other_unit_user)
    content = client.get(reverse("bookings:booking_detail", args=[booking.id])).content.decode()
    assert MEET_URL not in content
    assert "สอนออนไลน์วิชาทดสอบ" not in content


def test_guest_cannot_reach_link_anywhere(client, online_setup):
    *_, booking = online_setup
    resp = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert MEET_URL not in resp.content.decode()


def test_form_shows_url_field_only_for_online_rooms(online_setup):
    requester, _, _, _, online_room, classroom, _ = online_setup
    online_form = BookingForm(user=requester, room=online_room, instance=Booking(room=online_room))
    classroom_form = BookingForm(user=requester, room=classroom, instance=Booking(room=classroom))
    assert "online_meeting_url" in online_form.fields
    assert "online_meeting_url" not in classroom_form.fields


def test_notifications_never_embed_meeting_url(online_setup):
    *_, booking = online_setup
    from notifications.services import notify_submitted

    notify_submitted(booking)
    texts = list(Notification.objects.values_list("text", flat=True))
    assert texts, "ต้องมีการแจ้งเตือนถูกสร้าง"
    assert all("http" not in text for text in texts)
    # ลิงก์ในแจ้งเตือนต้องพาไปหน้ารายละเอียด (ซึ่งตรวจสิทธิ์อีกครั้ง) เท่านั้น
    assert all(
        url.startswith("/bookings/") for url in Notification.objects.values_list("url", flat=True) if url
    )


def test_online_meeting_url_is_editable_after_submit():
    assert "online_meeting_url" in POST_SUBMIT_EDITABLE_FIELDS


def test_homepage_shows_online_card_and_group_only_when_rooms_exist(client, online_setup):
    home = reverse("bookings:calendar")
    content = client.get(home).content.decode()
    assert 'id="now-online"' in content
    assert "ห้องสอนออนไลน์" in content

    Resource.objects.filter(room_category=Resource.Category.ONLINE).update(
        status=Resource.Status.RETIRED
    )
    content = client.get(home).content.decode()
    assert 'id="now-online"' not in content


def test_online_room_uses_same_overlap_protection(online_setup):
    """หมวดใหม่ต้องอยู่ใต้ ExclusionConstraint เดิม — จองชนต้องถูกปฏิเสธ"""
    requester, _, _, _, online_room, _, booking = online_setup
    from bookings.services import BookingConflict

    clash = Booking.objects.create(
        room=online_room, requester=requester, unit=requester.unit,
        responsible_name="ผู้ทดสอบ", responsible_phone="0812345678",
        title="ซ้อนเวลา",
        start_at=_aware(hour=10, minute=30), end_at=_aware(hour=11, minute=30),
    )
    with pytest.raises(BookingConflict):
        submit_booking(clash)

from datetime import timedelta
from html.parser import HTMLParser

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db

PASSWORD = "Password-2569"


class ServiceCardParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.current = None
        self.cards = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())
        if self.current is None and "lka-r3g-service" in classes:
            self.current = {"tag": tag, "href": attrs.get("href"), "links": []}
            self.depth = 1
            if tag == "a" and attrs.get("href"):
                self.current["links"].append(attrs["href"])
            return
        if self.current is not None:
            self.depth += 1
            if tag == "a" and attrs.get("href"):
                self.current["links"].append(attrs["href"])

    def handle_endtag(self, tag):
        if self.current is None:
            return
        self.depth -= 1
        if self.depth == 0:
            self.cards.append(self.current)
            self.current = None


def _user(username="a2-user"):
    unit = Unit.objects.create(code=f"A2-{username[:8]}", name=f"หน่วย {username}")
    return User.objects.create_user(
        username=username,
        email=f"{username}@signalschool.ac.th",
        password=PASSWORD,
        unit=unit,
        phone="0811111111",
    )


def _room(code="A2-R1", category=Resource.Category.CLASSROOM):
    room = Resource.objects.create(
        code=code,
        name=f"ห้อง {code}",
        building="อาคาร A2",
        floor="1",
        resource_type=Resource.Type.ROOM,
        room_category=category,
        capacity=20,
        status=Resource.Status.ACTIVE,
    )
    ResourceRule.objects.create(resource=room)
    return room


def _booking(*, user, room, start_offset_hours, status):
    start = timezone.now() + timedelta(hours=start_offset_hours)
    return Booking.objects.create(
        room=room,
        requester=user,
        unit=user.unit,
        responsible_name=user.display_name,
        responsible_phone=user.phone,
        title=f"งาน {start_offset_hours}",
        purpose=Booking.Purpose.TEACHING,
        start_at=start,
        end_at=start + timedelta(hours=1),
        request_status=status,
    )


def test_gateway_has_direct_task_destinations(client):
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")

    expected = (
        reverse("bookings:lodging_start"),
        reverse("bookings:online_teaching_home"),
        reverse("bookings:book_search") + "?category=classroom",
        reverse("bookings:book_search") + "?category=meeting",
    )
    for url in expected:
        assert f'href="{url}"' in html
    parser = ServiceCardParser()
    parser.feed(html)
    assert parser.cards[0]["tag"] == "a"
    assert parser.cards[0]["links"] == [reverse("bookings:lodging_start")]
    start_html = client.get(reverse("bookings:lodging_start")).content.decode()
    assert f'href="{reverse("bookings:lodging_index")}"' in start_html
    assert f'href="{reverse("bookings:lodging_general_request")}"' in start_html
    assert "วันนี้ต้องการทำอะไร" in html
    assert "ดูสถานะห้องทั้งหมด" in html
    assert "กำลังพัฒนาระบบ" not in html


def test_classroom_and_meeting_task_links_open_booking_search_when_logged_in(client):
    user = _user("a2-booker")
    client.force_login(user)
    for category in ("classroom", "meeting"):
        response = client.get(reverse("bookings:book_search"), {"category": category})
        assert response.status_code == 200


def test_every_service_card_has_a_real_link_and_none_points_to_calendar(client):
    html = client.get(reverse("bookings:lodging_about")).content.decode("utf-8")
    parser = ServiceCardParser()
    parser.feed(html)
    assert len(parser.cards) == 4
    calendar_url = reverse("bookings:calendar")
    for card in parser.cards:
        assert card["links"], card
        assert calendar_url not in card["links"]


def test_authenticated_gateway_replaces_private_count_row_with_pager(client):
    user = _user("a2-owner")
    other = _user("a2-other")
    room1 = _room("A2-C1")
    room2 = _room("A2-C2")
    _booking(user=user, room=room1, start_offset_hours=2, status=Booking.RequestStatus.PENDING)
    _booking(user=user, room=room2, start_offset_hours=4, status=Booking.RequestStatus.APPROVED)
    _booking(user=user, room=room1, start_offset_hours=6, status=Booking.RequestStatus.REJECTED)
    _booking(user=other, room=room2, start_offset_hours=8, status=Booking.RequestStatus.PENDING)

    client.force_login(user)
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert 'class="gateway-pager"' in html
    assert "มีข้อความ 0" in html
    assert "A2-C1" in html  # earliest active booking belongs to the signed-in user
    assert "A2-C2" not in html.split('class="gateway-pager"', 1)[1].split('</a>', 1)[0]
    assert reverse("bookings:my_bookings") in html
    cache_control = response.get("Cache-Control", "")
    assert "private" in cache_control
    assert "no-store" in cache_control


def test_anonymous_gateway_has_no_private_booking_row_or_no_store(client):
    response = client.get(reverse("bookings:lodging_about"))
    assert response.status_code == 200
    assert "การจองของฉัน" not in response.content.decode("utf-8")
    assert "no-store" not in response.get("Cache-Control", "")

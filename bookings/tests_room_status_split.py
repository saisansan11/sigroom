import pytest
from django.urls import reverse

from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def split_rooms():
    specs = [
        ("CLS-101", "ห้องเรียน 101", Resource.Category.CLASSROOM),
        ("LAB-101", "ห้องสอนปฏิบัติ 101", Resource.Category.LAB),
        ("MTG-101", "ห้องประชุม 101", Resource.Category.MEETING),
        ("SPC-101", "ห้องพิเศษ 101", Resource.Category.SPECIAL),
        ("STU-ONLINE-1", "ห้องสอนออนไลน์ 1", Resource.Category.ONLINE),
        ("DORM-401", "ห้องพัก 401", Resource.Category.LODGING),
    ]
    return [
        Resource.objects.create(
            code=code,
            name=name,
            resource_type=Resource.Type.ROOM,
            room_category=category,
            status=Resource.Status.ACTIVE,
            capacity=10,
        )
        for code, name, category in specs
    ]


def test_status_index_is_category_selector_not_combined_ledger(client, split_rooms):
    response = client.get(reverse("bookings:calendar"))
    assert response.status_code == 200
    html = response.content.decode("utf-8")

    assert "เลือกหมวดห้อง" in html
    assert 'id="today-board"' not in html
    assert "ทุกหมวดห้อง" not in html
    assert "category-chip" not in html
    for category in ("classroom", "lab", "meeting", "online", "lodging"):
        assert reverse("bookings:room_status", args=[category]) in html


@pytest.mark.parametrize(
    ("category", "expected", "excluded"),
    [
        ("classroom", {"CLS-101"}, {"LAB-101", "MTG-101", "SPC-101", "STU-ONLINE-1", "DORM-401"}),
        ("lab", {"LAB-101"}, {"CLS-101", "MTG-101", "SPC-101", "STU-ONLINE-1", "DORM-401"}),
        ("meeting", {"MTG-101", "SPC-101"}, {"CLS-101", "LAB-101", "STU-ONLINE-1", "DORM-401"}),
        ("online", {"STU-ONLINE-1"}, {"CLS-101", "LAB-101", "MTG-101", "SPC-101", "DORM-401"}),
        ("lodging", {"DORM-401"}, {"CLS-101", "LAB-101", "MTG-101", "SPC-101", "STU-ONLINE-1"}),
    ],
)
def test_each_status_page_is_server_locked_to_its_own_rooms(client, split_rooms, category, expected, excluded):
    response = client.get(reverse("bookings:room_status", args=[category]))
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    context_codes = {row["room"].code for row in response.context["board_rows"]}

    assert context_codes == expected
    for code in expected:
        assert code in html
    for code in excluded:
        assert code not in html
    assert "ทุกหมวดห้อง" not in html
    assert "category-chip" not in html


def test_query_string_cannot_switch_a_dedicated_status_page(client, split_rooms):
    url = reverse("bookings:room_status", args=["classroom"]) + "?category=lodging"
    response = client.get(url)
    assert response.status_code == 200
    codes = {row["room"].code for row in response.context["board_rows"]}
    assert codes == {"CLS-101"}
    assert "DORM-401" not in response.content.decode("utf-8")


def test_unknown_status_category_is_404(client, split_rooms):
    assert client.get(reverse("bookings:room_status", args=["all"])).status_code == 404


def test_status_calendar_feed_rejects_unknown_server_category(client, split_rooms):
    response = client.get(reverse("bookings:calendar_events"), {"status_category": "all"})
    assert response.status_code == 400


def test_dedicated_status_page_marks_status_nav_current(client, split_rooms):
    # เมนูแยกบริการ (PR #88): "สถานะห้อง" ของห้องเรียนชี้หน้าสถานะเฉพาะหมวดโดยตรง
    url = reverse("bookings:room_status", args=["classroom"])
    response = client.get(url)
    header = response.content.decode("utf-8").split('<header class="site-header">', 1)[1].split("</header>", 1)[0]
    assert f'<a href="{url}" aria-current="page">สถานะห้อง</a>' in header


def test_status_calendar_feed_does_not_leak_room_scoped_blackout(client, split_rooms):
    from datetime import timedelta
    from django.utils import timezone
    from resources.models import Blackout

    classroom = next(room for room in split_rooms if room.code == "CLS-101")
    lodging = next(room for room in split_rooms if room.code == "DORM-401")
    now = timezone.now()
    blackout = Blackout.objects.create(
        title="ปิดเฉพาะห้องพัก",
        start_at=now - timedelta(hours=1),
        end_at=now + timedelta(hours=1),
        scope=Blackout.Scope.ROOMS,
    )
    blackout.rooms.add(lodging)

    classroom_feed = client.get(
        reverse("bookings:calendar_events"),
        {"status_category": "classroom", "start": (now - timedelta(days=1)).isoformat(), "end": (now + timedelta(days=1)).isoformat()},
    )
    assert classroom_feed.status_code == 200
    assert all(item.get("title") != "ปิดเฉพาะห้องพัก (ห้องที่เลือก)" for item in classroom_feed.json())

    lodging_feed = client.get(
        reverse("bookings:calendar_events"),
        {"status_category": "lodging", "start": (now - timedelta(days=1)).isoformat(), "end": (now + timedelta(days=1)).isoformat()},
    )
    assert any(item.get("title") == "ปิดเฉพาะห้องพัก (ห้องที่เลือก)" for item in lodging_feed.json())


def test_status_calendar_feed_rejects_room_from_another_category(client, split_rooms):
    response = client.get(
        reverse("bookings:calendar_events"),
        {"status_category": "classroom", "room": "DORM-401"},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_online_status_does_not_expose_generic_gap_booking_links(client, split_rooms):
    response = client.get(reverse("bookings:room_status", args=["online"]))
    assert response.status_code == 200
    assert response.context["board_rows"]
    assert all(row["gaps"] == [] for row in response.context["board_rows"])
    html = response.content.decode("utf-8")
    assert "/book/STU-ONLINE-1/" not in html
    assert "ช่องประ" not in html

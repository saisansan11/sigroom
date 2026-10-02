"""ธีม A Ledger: ช่วงว่างแตะจองบนหน้าแรก, วันที่แบบเต็มเลขไทย และหน้าแรกแบบสมุดทะเบียน"""
from datetime import date, datetime, time, timedelta
from html import escape
from urllib.parse import parse_qs, urlparse

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.board import free_gaps
from bookings.models import Booking
from bookings.templatetags.thaidate import thai_date_full, thai_digits
from bookings.views import _countdown_label
from resources.models import Resource, ResourceRule

ZONE = timezone.get_current_timezone()


def at(hour, minute=0, day=date(2026, 10, 5)):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)), ZONE)


# ---------- ตัวช่วยคำนวณช่วงว่าง (pure) ----------

def test_free_gaps_whole_window_when_nothing_booked():
    gaps = free_gaps([], at(7), at(21))
    assert [(g.start, g.end) for g in gaps] == [(at(7), at(21))]


def test_free_gaps_split_around_bookings_and_merge_overlaps():
    busy = [(at(10), at(12)), (at(11), at(13)), (at(15), at(16))]
    gaps = free_gaps(busy, at(8), at(17))
    assert [(g.start, g.end) for g in gaps] == [(at(8), at(10)), (at(13), at(15)), (at(16), at(17))]


def test_free_gaps_clip_to_now_and_round_to_quarter():
    gaps = free_gaps([(at(14), at(15))], at(8), at(17), now=at(10, 7))
    assert [(g.start, g.end) for g in gaps] == [(at(10, 15), at(14)), (at(15), at(17))]


def test_free_gaps_skip_gaps_shorter_than_30_minutes():
    busy = [(at(9), at(10)), (at(10, 20), at(12))]
    gaps = free_gaps(busy, at(9), at(12, 45))
    # 10.00–10.20 สั้นเกินไป, 12.00–12.45 ยาวพอ
    assert [(g.start, g.end) for g in gaps] == [(at(12), at(12, 45))]


def test_free_gaps_respect_buffer_padding_visually():
    gaps = free_gaps([(at(10), at(11))], at(9), at(13), pad=timedelta(minutes=15))
    assert [(g.start, g.end) for g in gaps] == [(at(9), at(9, 45)), (at(11, 15), at(13))]


def test_free_gaps_empty_when_window_already_passed():
    assert free_gaps([], at(8), at(17), now=at(18)) == []


def test_free_gaps_ignore_busy_outside_window():
    gaps = free_gaps([(at(5), at(6)), (at(22), at(23))], at(8), at(17))
    assert [(g.start, g.end) for g in gaps] == [(at(8), at(17))]


# ---------- วันที่แบบเต็มเลขไทย / นับถอยหลัง ----------

def test_thai_date_full_uses_thai_numerals_and_weekday():
    assert thai_date_full(date(2026, 10, 2)) == "วันศุกร์ที่ ๒ ตุลาคม พ.ศ. ๒๕๖๙"
    assert thai_digits("10.42") == "๑๐.๔๒"


def test_countdown_label():
    class B:
        start_at = at(13)
        end_at = at(16)
    assert _countdown_label(B, at(10, 42)) == "อีก 2 ชม. 18 นาที"
    assert _countdown_label(B, at(12, 50)) == "อีก 10 นาที"
    assert _countdown_label(B, at(14)) == "กำลังใช้อยู่ ถึง 16.00 น."
    assert _countdown_label(None, at(10)) == ""


# ---------- หน้าแรกแสดงช่วงว่างเป็นลิงก์จอง ----------

@pytest.fixture
def ledger_home(db, monkeypatch):
    today = timezone.localdate()
    fixed_now = timezone.make_aware(datetime.combine(today, time(8, 0)), ZONE)
    monkeypatch.setattr("django.utils.timezone.now", lambda: fixed_now)
    unit = Unit.objects.create(code="LG", name="หน่วยทดสอบธีม A")
    user = User.objects.create_user("ledger_user", "ledger@signalschool.ac.th", "Password-2569", unit=unit)
    room = Resource.objects.create(
        code="LG-101", name="ห้องเรียนทะเบียน", resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.CLASSROOM, capacity=40,
    )
    ResourceRule.objects.create(resource=room, service_start=time(7, 30), service_end=time(17, 0))
    dorm = Resource.objects.create(
        code="LG-DORM", name="ห้องพักทะเบียน", resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING, capacity=4,
    )
    Booking.objects.create(
        room=room, requester=user, unit=unit, title="สอนวิชาสื่อสาร",
        start_at=timezone.make_aware(datetime.combine(today, time(10, 0)), ZONE),
        end_at=timezone.make_aware(datetime.combine(today, time(12, 0)), ZONE),
        request_status=Booking.RequestStatus.APPROVED,
    )
    return {"today": today, "user": user, "room": room, "dorm": dorm}


def _row(response, code):
    return next(row for row in response.context["board_rows"] if row["room"].code == code)


def _query(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def test_home_board_links_free_gaps_to_prefilled_booking_form(client, ledger_home):
    client.force_login(ledger_home["user"])
    response = client.get(reverse("bookings:calendar"))
    assert response.status_code == 200

    gaps = _row(response, "LG-101")["gaps"]
    assert [(_query(g["url"])["start"], _query(g["url"])["end"]) for g in gaps] == [("08:00", "10:00"), ("12:00", "17:00")]
    first = gaps[0]["url"]
    assert first.startswith(reverse("bookings:book_form", args=["LG-101"]) + "?")
    assert _query(first)["date"] == ledger_home["today"].isoformat()

    html = response.content.decode()
    assert 'class="slot slot-free"' in html
    assert escape(first) in html
    assert 'class="slot slot-approved"' in html
    assert "ทะเบียนห้องวันนี้" in html


def test_home_board_free_gap_link_prefills_the_form(client, ledger_home):
    client.force_login(ledger_home["user"])
    gap_url = _row(client.get(reverse("bookings:calendar")), "LG-101")["gaps"][1]["url"]
    form = client.get(gap_url).context["form"]
    assert form.initial["start_time"] == "12:00"
    assert form.initial["end_time"] == "17:00"


def test_home_board_free_gaps_send_anonymous_users_to_login(client, ledger_home):
    response = client.get(reverse("bookings:calendar"))
    gaps = _row(response, "LG-101")["gaps"]
    assert gaps
    assert all(g["url"].startswith(reverse("login") + "?next=") for g in gaps)
    assert "เข้าสู่ระบบเพื่อจอง" in response.content.decode()


def test_home_board_has_no_free_gap_links_for_lodging_rooms(client, ledger_home):
    client.force_login(ledger_home["user"])
    response = client.get(reverse("bookings:calendar"))
    assert _row(response, "LG-DORM")["gaps"] == []


def test_home_board_marks_pending_and_outage_without_relying_on_colour(client, ledger_home):
    from resources.models import ResourceOutage

    today = ledger_home["today"]
    Booking.objects.create(
        room=ledger_home["room"], requester=ledger_home["user"], unit=ledger_home["user"].unit,
        title="ฝึก นนส.", request_status=Booking.RequestStatus.PENDING,
        start_at=timezone.make_aware(datetime.combine(today, time(14, 0)), ZONE),
        end_at=timezone.make_aware(datetime.combine(today, time(15, 0)), ZONE),
    )
    ResourceOutage.objects.create(
        resource=ledger_home["dorm"], reason="ซ่อมเครื่องปรับอากาศ", created_by=ledger_home["user"],
        start_at=timezone.make_aware(datetime.combine(today, time(9, 0)), ZONE),
        end_at=timezone.make_aware(datetime.combine(today, time(11, 0)), ZONE),
    )
    client.force_login(ledger_home["user"])
    html = client.get(reverse("bookings:calendar")).content.decode()
    assert "รอพิจารณา · ฝึก นนส." in html
    assert "งดใช้ · ซ่อมเครื่องปรับอากาศ" in html
    gaps = _row(client.get(reverse("bookings:calendar")), "LG-101")["gaps"]
    assert [(_query(g["url"])["start"], _query(g["url"])["end"]) for g in gaps] == [
        ("08:00", "10:00"), ("12:00", "14:00"), ("15:00", "17:00"),
    ]

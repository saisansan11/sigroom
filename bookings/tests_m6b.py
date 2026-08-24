"""
ทดสอบหน้าแรกแบบ command board (M6-B1): แถบสถิติและแถวเวลารายห้องวันนี้
รัน: uv run pytest bookings/tests_m6b.py

เทสทั้งไฟล์ freeze เวลาไว้ที่ 10:00 ของวันปัจจุบัน เพื่อให้ผลแน่นอนไม่ขึ้นกับเวลาจริงที่รัน
"""
from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from resources.models import Resource, ResourceOutage, ResourceRule

pytestmark = pytest.mark.django_db

FROZEN_LOCAL_10 = timezone.make_aware(
    timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0).replace(tzinfo=None),
    timezone.get_current_timezone(),
)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch):
    """ตรึง timezone.now ให้เป็น 10:00 วันนี้ ทั้งใน view และ service ที่ถูกเรียกระหว่าง request"""
    monkeypatch.setattr(timezone, "now", lambda: FROZEN_LOCAL_10)
    return FROZEN_LOCAL_10


@pytest.fixture
def unit():
    return Unit.objects.create(code="COMM", name="แผนกวิชาการสื่อสาร")


@pytest.fixture
def user(unit):
    return User.objects.create_user(username="somchai", email="somchai@signalschool.ac.th", password="x" * 12, unit=unit)


@pytest.fixture
def rooms():
    made = []
    for code in ("MTG-1", "MTG-2", "MTG-3", "LAB-1"):
        r = Resource.objects.create(code=code, name=f"ห้อง {code}", room_category=Resource.Category.MEETING)
        ResourceRule.objects.create(resource=r)
        made.append(r)
    return made


def _booking(user, unit, room, start, hours=1, **kw):
    return Booking.objects.create(
        room=room, requester=user, unit=unit, responsible_name="ร.อ.สมชาย", responsible_phone="081",
        title="ประชุมเตรียมการฝึก", start_at=start, end_at=start + timedelta(hours=hours), **kw,
    )


def test_homepage_board_counts_and_blocks(client, user, unit, rooms):
    now = FROZEN_LOCAL_10
    # MTG-1: อนุมัติแล้วและคร่อมเวลาปัจจุบัน → กำลังใช้ ไม่ว่าง
    _booking(user, unit, rooms[0], now - timedelta(minutes=30), hours=2,
             request_status=Booking.RequestStatus.APPROVED)
    # MTG-2: รออนุมัติคร่อมเวลาปัจจุบัน → ถือครองเวลา (FR-10) ต้องไม่นับว่าว่าง แต่ไม่ใช่ "กำลังใช้"
    _booking(user, unit, rooms[1], now - timedelta(minutes=15), hours=1,
             request_status=Booking.RequestStatus.PENDING)
    # MTG-3: รออนุมัติช่วงบ่าย → ตอนนี้ยังว่าง
    _booking(user, unit, rooms[2], now + timedelta(hours=3),
             request_status=Booking.RequestStatus.PENDING)
    # LAB-1: มีทั้ง booking กำลังใช้และ outage คร่อมเวลาปัจจุบัน → ต้องหักออกครั้งเดียว ไม่หักซ้ำ
    _booking(user, unit, rooms[3], now - timedelta(hours=1), hours=3,
             request_status=Booking.RequestStatus.APPROVED)
    ResourceOutage.objects.create(
        resource=rooms[3], start_at=now - timedelta(hours=1), end_at=now + timedelta(hours=1),
        reason="ซ่อมเครื่องปรับอากาศ", created_by=user,
    )
    client.force_login(user)
    response = client.get("/")
    assert response.status_code == 200
    ctx = response.context
    assert ctx["stat_total"] == 4
    assert ctx["stat_in_use"] == 2          # MTG-1, LAB-1 อนุมัติและคร่อมเวลาปัจจุบัน
    assert ctx["stat_free_now"] == 1        # เหลือ MTG-3 เท่านั้น (MTG-2 pending คร่อมตอนนี้, LAB-1 ไม่ถูกหักซ้ำ)
    assert ctx["my_pending_count"] == 2
    blocks_by_room = {row["room"].code: row["blocks"] for row in ctx["board_rows"]}
    assert [b["cls"] for b in blocks_by_room["MTG-1"]] == ["in-use"]
    assert [b["cls"] for b in blocks_by_room["MTG-2"]] == ["pending"]
    assert [b["cls"] for b in blocks_by_room["MTG-3"]] == ["pending"]
    assert sorted(b["cls"] for b in blocks_by_room["LAB-1"]) == ["in-use", "outage"]
    # ผู้จองเห็นชื่อเรื่องของตัวเอง และตำแหน่งแท่งอยู่ในช่วง 0–100%
    assert blocks_by_room["MTG-1"][0]["label"] == "ประชุมเตรียมการฝึก"
    for blocks in blocks_by_room.values():
        for b in blocks:
            assert 0 <= b["left"] <= 100 and b["width"] > 0
    assert ctx["board_now_pct"] is not None


def test_homepage_board_masks_restricted_titles(client, unit, rooms):
    now = FROZEN_LOCAL_10
    other_unit = Unit.objects.create(code="EW", name="แผนกวิชา EW")
    owner = User.objects.create_user(username="wanida", email="wanida@signalschool.ac.th", password="x" * 12, unit=other_unit)
    viewer = User.objects.create_user(username="prasit", email="prasit@signalschool.ac.th", password="x" * 12, unit=unit)
    _booking(owner, other_unit, rooms[0], now - timedelta(minutes=30), hours=2,
             request_status=Booking.RequestStatus.APPROVED, visibility=Booking.Visibility.RESTRICTED)
    client.force_login(viewer)
    ctx = client.get("/").context
    blocks_by_room = {row["room"].code: row["blocks"] for row in ctx["board_rows"]}
    assert blocks_by_room["MTG-1"][0]["label"] == "ไม่ว่าง"

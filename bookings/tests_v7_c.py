"""เทสงาน C (แผน V7): จองแบบเดิมอีกครั้ง + ช่วงเวลาสำเร็จรูป + ห้องโปรด"""
from datetime import date, datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking, ReferenceValue, parse_time_preset
from bookings.services import find_available_rooms, rebook_default_date, submit_booking, time_presets
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


def _aware(y=2026, m=9, d=1, hour=10, minute=0):
    return timezone.make_aware(datetime(y, m, d, hour, minute), timezone.get_current_timezone())


@pytest.fixture
def rebook_setup():
    unit = Unit.objects.create(code="V7C-EDU", name="หน่วยทดสอบงาน C")
    user = User.objects.create_user(
        username="v7c-user", email="v7c-user@signalschool.ac.th",
        password="Password-2569", unit=unit, phone="0812345678",
    )

    def make_room(code):
        room = Resource.objects.create(
            code=code, name=f"ห้อง {code}", resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.CLASSROOM, building="อาคารทดสอบ",
            capacity=20, owner_unit=unit,
        )
        ResourceRule.objects.create(resource=room, service_start=time(7), service_end=time(21))
        return room

    rooms = [make_room(f"V7C-R{i}") for i in range(3)]
    return user, unit, rooms


# ---------- สูตรวันที่จองซ้ำ ----------

def test_rebook_date_last_week_gets_plus_seven():
    assert rebook_default_date(date(2026, 9, 1), today=date(2026, 9, 5)) == date(2026, 9, 8)


def test_rebook_date_old_booking_lands_next_week_not_past():
    # จองเก่าเมื่อเดือนก่อน ต้องได้วันเดียวกันของสัปดาห์หน้า (อังคาร) ไม่ใช่วันในอดีต
    result = rebook_default_date(date(2026, 8, 4), today=date(2026, 9, 5))
    assert result == date(2026, 9, 8)
    assert result > date(2026, 9, 5)
    assert result.weekday() == date(2026, 8, 4).weekday()


def test_rebook_date_tomorrow_original_still_moves_a_full_week():
    # ต้นฉบับเป็นวันพรุ่งนี้ → ได้พรุ่งนี้ของสัปดาห์ถัดไป ไม่ใช่วันพรุ่งนี้ซ้ำ (กันชนกับใบต้นฉบับ)
    assert rebook_default_date(date(2026, 9, 6), today=date(2026, 9, 5)) == date(2026, 9, 13)


def test_rebook_view_prefills_everything_with_future_date(client, rebook_setup):
    user, unit, rooms = rebook_setup
    room = rooms[0]
    old_start = _aware(m=8, d=4, hour=13)  # เดือนก่อน
    booking = Booking.objects.create(
        room=room, requester=user, unit=unit,
        responsible_name="ผู้ทดสอบ ระบบ", responsible_phone="0812345678",
        title="วิชาประจำสัปดาห์", attendees=25, layout="แถวหน้ากระดาน",
        start_at=old_start, end_at=old_start + timedelta(hours=2),
        request_status=Booking.RequestStatus.APPROVED,  # การจองเดือนก่อนที่จบไปแล้ว
    )
    client.force_login(user)

    resp = client.get(
        reverse("bookings:book_form", args=[room.code]), {"rebook": str(booking.id)}
    )
    form = resp.context["form"]
    assert form.initial["title"] == "วิชาประจำสัปดาห์"
    assert form.initial["start_time"] == "13:00"
    assert form.initial["end_time"] == "15:00"
    assert form.initial["attendees"] == 25
    new_date = form.initial["date"]
    assert new_date > timezone.localdate()
    assert new_date.weekday() == timezone.localtime(old_start).date().weekday()


def test_rebook_rejects_other_users_booking(client, rebook_setup):
    user, unit, rooms = rebook_setup
    stranger = User.objects.create_user(
        username="v7c-stranger", email="v7c-stranger@signalschool.ac.th",
        password="Password-2569", unit=unit,
    )
    room = rooms[0]
    booking = Booking.objects.create(
        room=room, requester=stranger, unit=unit,
        responsible_name="คนอื่น", responsible_phone="0899999999",
        title="ของคนอื่น",
        start_at=_aware(d=1, hour=9), end_at=_aware(d=1, hour=10),
    )
    client.force_login(user)
    resp = client.get(reverse("bookings:book_form", args=[room.code]), {"rebook": str(booking.id)})
    assert resp.context["form"].initial.get("title") != "ของคนอื่น"


def test_my_bookings_shows_rebook_link_only_for_approved(client, rebook_setup):
    user, unit, rooms = rebook_setup
    approved = Booking.objects.create(
        room=rooms[0], requester=user, unit=unit,
        responsible_name="ผู้ทดสอบ", responsible_phone="0812345678", title="อนุมัติแล้ว",
        start_at=timezone.now() + timedelta(days=1, hours=1),
        end_at=timezone.now() + timedelta(days=1, hours=2),
        request_status=Booking.RequestStatus.APPROVED,
    )
    Booking.objects.create(
        room=rooms[1], requester=user, unit=unit,
        responsible_name="ผู้ทดสอบ", responsible_phone="0812345678", title="ร่าง",
        start_at=timezone.now() + timedelta(days=2, hours=1),
        end_at=timezone.now() + timedelta(days=2, hours=2),
        request_status=Booking.RequestStatus.DRAFT,
    )
    client.force_login(user)
    content = client.get(reverse("bookings:my_bookings")).content.decode()
    assert f"rebook={approved.id}" in content


# ---------- ช่วงเวลาสำเร็จรูป ----------

def test_parse_time_preset_accepts_valid_and_rejects_invalid():
    assert parse_time_preset("0800-1200|คาบเช้า") == ("08:00", "12:00", "คาบเช้า")
    for bad in ("08001200|x", "0800-1200", "1200-0800|กลับด้าน", "0807-1200|ไม่ตรง 15 นาที", "2500-2600|เกินวัน", "0800-0800|เท่ากัน"):
        assert parse_time_preset(bad) is None, bad


def test_reference_value_clean_validates_time_preset():
    from django.core.exceptions import ValidationError

    ok = ReferenceValue(field="time_preset", value="0800-1200|คาบเช้า")
    ok.clean()  # ต้องไม่ raise
    with pytest.raises(ValidationError):
        ReferenceValue(field="time_preset", value="ผิดรูปแบบ").clean()


def test_time_presets_reads_admin_rows_and_falls_back_to_defaults():
    labels = [preset["label"] for preset in time_presets()]
    assert labels == ["คาบเช้า", "คาบบ่าย", "ทั้งวัน"]  # ไม่มีแถวใน Admin → ใช้ค่า default

    ReferenceValue.objects.create(field="time_preset", value="0700-0800|เช้าตรู่", order=1)
    ReferenceValue.objects.create(field="time_preset", value="0900-1000|ปิดใช้", order=2, is_active=False)
    presets = time_presets()
    assert [p["label"] for p in presets] == ["เช้าตรู่"]
    assert presets[0]["start"] == "07:00" and presets[0]["end"] == "08:00"


def test_search_page_renders_presets_but_summary_mode_does_not(client, rebook_setup):
    user, _, rooms = rebook_setup
    client.force_login(user)
    assert "time-preset-button" in client.get(reverse("bookings:book_search")).content.decode()

    # ฟอร์มจองโหมดสรุป (มาจากผลค้นหาพร้อมวันเวลา) ต้องไม่มีปุ่มคาบ
    resp = client.get(
        reverse("bookings:book_form", args=[rooms[0].code]),
        {"search": "1", "date": (timezone.localdate() + timedelta(days=1)).isoformat(), "start": "09:00", "end": "10:00"},
    )
    content = resp.content.decode()
    assert "สรุปการจอง" in content
    assert "time-preset-button" not in content


# ---------- ห้องโปรด ----------

def test_favorites_sort_first_in_available_rooms(rebook_setup):
    user, _, rooms = rebook_setup
    start = timezone.now() + timedelta(days=1)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)

    available, _ = find_available_rooms(start, end, user)
    assert [r.room.code for r in available] == ["V7C-R0", "V7C-R1", "V7C-R2"]

    user.favorite_resources.add(rooms[2])
    available, _ = find_available_rooms(start, end, user)
    assert available[0].room.code == "V7C-R2"


def test_favorite_toggle_adds_and_removes_own_rooms_only(client, rebook_setup):
    user, _, rooms = rebook_setup
    other = User.objects.create_user(
        username="v7c-other", email="v7c-other@signalschool.ac.th", password="Password-2569"
    )
    client.force_login(user)
    url = reverse("bookings:room_favorite_toggle", args=[rooms[0].code])

    client.post(url, {"next": reverse("bookings:book_search")})
    assert user.favorite_resources.filter(pk=rooms[0].pk).exists()
    assert not other.favorite_resources.exists()  # ไม่กระทบคนอื่น

    client.post(url, {"next": reverse("bookings:book_search")})
    assert not user.favorite_resources.filter(pk=rooms[0].pk).exists()


def test_favorite_toggle_rejects_external_next_url(client, rebook_setup):
    user, _, rooms = rebook_setup
    client.force_login(user)
    resp = client.post(
        reverse("bookings:room_favorite_toggle", args=[rooms[0].code]),
        {"next": "https://evil.example.com/"},
    )
    assert resp.status_code == 302
    assert resp.url == reverse("bookings:book_search")

"""หน้าขอใช้ห้อง 3 ขั้นในหน้าเดียว (ธีม A): ชิปวัน/ช่วงเวลา, คำแนะนำเวลาอื่น, ค่าผู้รับผิดชอบเดิม,
ตราประทับผลการขอ (ครั้งเดียว) และไฟล์ .ics"""
from datetime import date, datetime, time, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.forms import BookingForm
from bookings.ics import booking_ics
from bookings.models import Booking
from bookings.services import (
    booking_suggestions,
    find_available_rooms,
    last_booking_defaults,
    nearest_free_slot,
    next_available_date,
    resolve_search_selection,
    search_date_choices,
    submit_booking,
)
from resources.models import Blackout, Resource, ResourceOutage, ResourceRule

pytestmark = pytest.mark.django_db
ZONE = timezone.get_current_timezone()


def next_monday(min_days=7):
    day = timezone.localdate() + timedelta(days=min_days)
    while day.weekday() != 0:
        day += timedelta(days=1)
    return day


def at(day, hour, minute=0):
    return timezone.make_aware(datetime.combine(day, time(hour, minute)), ZONE)


def make_room(code, *, policy=ResourceRule.ApprovalPolicy.AUTO, before=0, after=0, capacity=30, category=Resource.Category.CLASSROOM):
    room = Resource.objects.create(code=code, name=f"ห้อง {code}", building="อาคารทดสอบ", capacity=capacity, room_category=category)
    ResourceRule.objects.create(
        resource=room,
        approval_policy=policy,
        service_start=time(7, 30),
        service_end=time(17, 0),
        buffer_before_min=before,
        buffer_after_min=after,
    )
    return Resource.objects.select_related("rule").get(pk=room.pk)


def book(room, user, start, end, title="จองไว้แล้ว", **extra):
    booking = Booking.objects.create(
        room=room,
        requester=user,
        unit=user.unit,
        responsible_name=extra.pop("responsible_name", user.display_name),
        responsible_phone=extra.pop("responsible_phone", "081-000-0000"),
        title=title,
        start_at=start,
        end_at=end,
        **extra,
    )
    return submit_booking(booking)


@pytest.fixture
def flow():
    unit = Unit.objects.create(code="FLOW", name="แผนกทดสอบขั้นตอน")
    other_unit = Unit.objects.create(code="OTHER", name="หน่วยอื่น")
    user = User.objects.create_user(
        username="flow_user", email="flow_user@signalschool.ac.th", password="Password-2569",
        unit=unit, rank="ร.ท.", first_name="ทดสอบ", last_name="ขั้นตอน", phone="081-111-1111",
    )
    other = User.objects.create_user(
        username="flow_other", email="flow_other@signalschool.ac.th", password="Password-2569",
        unit=other_unit, rank="ร.ต.", first_name="คน", last_name="อื่น",
    )
    return {"unit": unit, "other_unit": other_unit, "user": user, "other": other}


# ---------- ชิปวัน / ช่วงเวลา → วันเวลาที่ค้นหา ----------

def test_date_chips_today_tomorrow_then_next_four_weekdays():
    friday = date(2026, 10, 2)
    choices = search_date_choices(friday)
    assert [c["date"] for c in choices] == [
        date(2026, 10, 2), date(2026, 10, 3), date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7), date(2026, 10, 8),
    ]
    assert choices[0]["label"] == "วันนี้" and choices[1]["label"] == "พรุ่งนี้"
    assert choices[2]["label"] == "จ. 5 ต.ค."
    assert choices[1]["sub"] == "ส. 3 ต.ค."


def test_chips_resolve_to_start_and_end():
    today = date(2026, 10, 2)
    selection = resolve_search_selection(QueryDict("day=2026-10-06&period=13:00-16:00"), today=today)
    assert selection.error == ""
    assert selection.date == date(2026, 10, 6)
    assert (selection.start_time, selection.end_time) == ("13:00", "16:00")
    assert selection.day_choice == "2026-10-06" and selection.period_choice == "13:00-16:00"
    assert selection.start_at == at(date(2026, 10, 6), 13)
    assert selection.end_at == at(date(2026, 10, 6), 16)
    whole_day = resolve_search_selection(QueryDict("day=2026-10-06&period=08:00-16:30"), today=today)
    assert (whole_day.start_time, whole_day.end_time) == ("08:00", "16:30")


def test_chip_wins_over_raw_fields_and_custom_uses_selects():
    today = date(2026, 10, 2)
    chip = resolve_search_selection(QueryDict("day=2026-10-05&date=20/10/2569&period=08:00-12:00&start=10:00&end=11:00"), today=today)
    assert chip.date == date(2026, 10, 5) and chip.start_time == "08:00"
    custom = resolve_search_selection(QueryDict("day=other&date=20/10/2569&period=custom&start=10:15&end=11:45"), today=today)
    assert custom.date == date(2026, 10, 20)
    assert (custom.start_time, custom.end_time) == ("10:15", "11:45")
    assert custom.day_choice == "other" and custom.period_choice == "custom"


def test_legacy_links_select_matching_chips_and_defaults():
    today = date(2026, 10, 2)
    legacy = resolve_search_selection(QueryDict("search=1&date=2026-10-05&start=08:00&end=12:00"), today=today)
    assert legacy.day_choice == "2026-10-05" and legacy.period_choice == "08:00-12:00"
    odd = resolve_search_selection(QueryDict("date=2026-10-30&start=09:00&end=10:00"), today=today)
    assert odd.day_choice == "other" and odd.period_choice == "custom" and odd.date_text == "30/10/2569"
    default = resolve_search_selection(QueryDict(""), today=today)
    assert default.date == date(2026, 10, 3) and (default.start_time, default.end_time) == ("08:00", "12:00")


def test_invalid_selection_reports_thai_error():
    today = date(2026, 10, 2)
    assert resolve_search_selection(QueryDict("day=other&date="), today=today).error
    assert "หลังเวลาเริ่ม" in resolve_search_selection(QueryDict("period=custom&start=11:00&end=10:00"), today=today).error
    assert resolve_search_selection(QueryDict("date=99/99/2569"), today=today).start_at is None


def test_book_search_view_uses_chips_and_links_form_with_legacy_params(client, flow):
    room = make_room("CHIP-1")
    day = next_monday()
    client.force_login(flow["user"])
    response = client.get(reverse("bookings:book_search"), {"day": "other", "date": day.isoformat(), "period": "13:00-16:00", "attendees": "12"})
    assert response.status_code == 200
    html = response.content.decode()
    assert "ห้องที่ว่าง" in html and room.code in html
    link = reverse("bookings:book_form", args=[room.code])
    href = html.split(f'href="{link}?', 1)[1].split('"', 1)[0].replace("&amp;", "&")
    params = parse_qs(href)
    assert params["date"] == [day.isoformat()]
    assert params["start"] == ["13:00"] and params["end"] == ["16:00"] and params["attendees"] == ["12"]
    # แถบเวลาเล็ก: ช่วงที่ขอ (หมึก)
    assert 'class="mt-req"' in html


def test_book_search_htmx_returns_results_partial_only(client, flow):
    make_room("CHIP-2")
    client.force_login(flow["user"])
    response = client.get(reverse("bookings:book_search"), {"period": "08:00-12:00"}, headers={"HX-Request": "true"})
    html = response.content.decode()
    assert "<html" not in html
    assert "results-title" in html


def test_mini_track_shows_other_bookings_grey(client, flow):
    room = make_room("TRACK-1")
    day = next_monday()
    book(room, flow["user"], at(day, 8), at(day, 9))
    client.force_login(flow["user"])
    html = client.get(reverse("bookings:book_search"), {"date": day.isoformat(), "start": "13:00", "end": "14:00"}).content.decode()
    assert 'class="mt-busy"' in html
    assert "มีการจองอื่น 08.00–09.00 น." in html


# ---------- คำแนะนำเวลาอื่น ----------

def test_nearest_free_slot_shifts_same_duration_same_day(flow):
    room = make_room("SHIFT-1")
    day = next_monday()
    book(room, flow["other"], at(day, 13), at(day, 14))
    slot = nearest_free_slot(room, at(day, 13), at(day, 16), flow["user"])
    assert slot == (at(day, 14), at(day, 17))


def test_nearest_free_slot_respects_buffers(flow):
    room = make_room("SHIFT-BUF", after=30)
    day = next_monday()
    book(room, flow["other"], at(day, 13), at(day, 14))
    # ถ้าไม่คิด buffer จะได้ 14:00–16:00 แต่ห้องต้องเก็บถึง 14:30
    assert nearest_free_slot(room, at(day, 13), at(day, 15), flow["user"]) == (at(day, 14, 30), at(day, 16, 30))


def test_nearest_free_slot_respects_outage_and_blackout(flow):
    room = make_room("SHIFT-OUT")
    day = next_monday()
    book(room, flow["other"], at(day, 13), at(day, 14))
    ResourceOutage.objects.create(resource=room, start_at=at(day, 14), end_at=at(day, 17), reason="ซ่อมแอร์", created_by=flow["other"])
    assert nearest_free_slot(room, at(day, 13), at(day, 15), flow["user"]) == (at(day, 11), at(day, 13))
    Blackout.objects.create(title="พิธีประจำปี", start_at=at(day, 7), end_at=at(day, 13), created_by=flow["other"])
    assert nearest_free_slot(room, at(day, 13), at(day, 15), flow["user"]) is None


def test_next_available_date_skips_full_days_and_weekends(flow):
    room = make_room("NEXT-1")
    monday = next_monday()
    book(room, flow["other"], at(monday, 9), at(monday, 10))
    book(room, flow["other"], at(monday + timedelta(days=1), 9), at(monday + timedelta(days=1), 10))
    found = next_available_date(at(monday, 9), at(monday, 10), flow["user"], room_categories=(Resource.Category.CLASSROOM,))
    assert found == (at(monday + timedelta(days=2), 9), at(monday + timedelta(days=2), 10), 1)
    friday = monday + timedelta(days=4)
    book(room, flow["other"], at(friday, 9), at(friday, 10))
    after_friday = next_available_date(at(friday, 9), at(friday, 10), flow["user"])
    assert after_friday[0].date() == friday + timedelta(days=3)  # ข้ามเสาร์-อาทิตย์


def test_suggestions_prefer_frequent_room_and_add_next_date_when_full(flow):
    room = make_room("FREQ-1")
    # min_days=8 ให้วันก่อนหน้า 7 วันยังเป็นอนาคตเสมอ (เดิมรันวันจันทร์แล้วไปจองเช้าวันนี้ซึ่งผ่านไปแล้ว)
    day = next_monday(min_days=8)
    past_day = day - timedelta(days=7)
    for hour in (8, 9):
        book(room, flow["user"], at(past_day, hour), at(past_day, hour + 1))
    book(room, flow["other"], at(day, 13), at(day, 14))
    available, unavailable = find_available_rooms(at(day, 13), at(day, 16), flow["user"])
    assert available == [] and unavailable[0].time_conflict_only is True
    suggestions = booking_suggestions(flow["user"], at(day, 13), at(day, 16), available, unavailable)
    kinds = [item.kind for item in suggestions]
    assert kinds == ["shift", "next_date"]
    assert suggestions[0].room == room and suggestions[0].frequent is True
    assert (suggestions[0].start_at, suggestions[0].end_at) == (at(day, 14), at(day, 17))
    assert suggestions[1].start_at == at(day + timedelta(days=1), 13)


def test_suggestions_skip_rooms_that_fail_for_other_rules(flow):
    room = make_room("RULE-1")
    day = next_monday()
    ResourceOutage.objects.create(resource=room, start_at=at(day, 7), end_at=at(day, 17), reason="ปิดซ่อม", created_by=flow["other"])
    available, unavailable = find_available_rooms(at(day, 13), at(day, 14), flow["user"])
    assert unavailable[0].time_conflict_only is False
    assert [s.kind for s in booking_suggestions(flow["user"], at(day, 13), at(day, 14), available, unavailable)] in ([], ["next_date"])


def test_suggestion_link_rendered_on_search_page(client, flow):
    room = make_room("LINK-1")
    day = next_monday()
    book(room, flow["other"], at(day, 13), at(day, 14))
    client.force_login(flow["user"])
    html = client.get(reverse("bookings:book_search"), {"date": day.isoformat(), "start": "13:00", "end": "16:00"}).content.decode()
    assert "ว่างถ้าเลื่อนเป็น" in html and "14.00–17.00 น." in html
    assert "ใช้เวลานี้แทน" in html
    assert f"{reverse('bookings:book_form', args=[room.code])}?date={day.isoformat()}&amp;start=14%3A00&amp;end=17%3A00" in html


# ---------- ค่าผู้รับผิดชอบจากการจองครั้งก่อน ----------

def test_last_booking_defaults_fall_back_to_profile(flow):
    defaults = last_booking_defaults(flow["user"])
    assert defaults == {
        "responsible_name": flow["user"].display_name,
        "responsible_phone": "081-111-1111",
        "unit": flow["unit"].pk,
        "source": "profile",
    }


def test_last_booking_defaults_use_most_recent_booking(flow):
    room = make_room("LAST-1")
    day = next_monday()
    book(room, flow["user"], at(day, 8), at(day, 9), responsible_name="ร.อ.คนเก่า", responsible_phone="02-000")
    book(room, flow["user"], at(day, 10), at(day, 11), responsible_name="ร.ท.คนล่าสุด", responsible_phone="089-999-9999")
    defaults = last_booking_defaults(flow["user"])
    assert defaults["responsible_name"] == "ร.ท.คนล่าสุด"
    assert defaults["responsible_phone"] == "089-999-9999"
    assert defaults["source"] == "last_booking"


def test_book_form_prefills_from_last_booking_and_shows_summary(client, flow):
    room = make_room("FORM-1")
    day = next_monday()
    book(room, flow["user"], at(day, 8), at(day, 9), responsible_name="ร.ท.ผู้ประสาน", responsible_phone="089-222-3333")
    client.force_login(flow["user"])
    response = client.get(reverse("bookings:book_form", args=[room.code]), {"date": day.isoformat(), "start": "13:00", "end": "14:00"})
    form = response.context["form"]
    assert form.initial["responsible_name"] == "ร.ท.ผู้ประสาน"
    assert form.initial["responsible_phone"] == "089-222-3333"
    assert form.initial["start_time"] == "13:00" and form.initial["end_time"] == "14:00"
    html = response.content.decode()
    assert "ดึงจากการจองครั้งก่อนให้แล้ว" in html
    assert "ช่องเดียวที่ต้องกรอก" in html
    # ประเภทการใช้/จำนวนคน ย้ายไปอยู่ในตัวเลือกเพิ่มเติม (พับไว้)
    more = html.split('<details class="form-more ledger-disclosure"', 1)[1]
    assert more.split(">", 1)[0].strip() == ""  # ไม่ได้เปิดค้าง
    assert 'name="purpose"' in more and 'name="attendees"' in more


def test_book_form_falls_back_when_last_unit_no_longer_allowed(flow):
    room = make_room("FORM-2")
    form = BookingForm(
        user=flow["user"], room=room, instance=Booking(room=room, requester=flow["user"], unit=flow["unit"]),
        initial={"unit": flow["other_unit"].pk},
    )
    assert form.initial["unit"] == flow["unit"].pk


def test_book_form_more_section_opens_on_attendees_error(client, flow):
    room = make_room("FORM-3")
    day = next_monday()
    client.force_login(flow["user"])
    response = client.post(reverse("bookings:book_form", args=[room.code]), {
        "date": day.isoformat(), "start_time": "09:00", "end_time": "10:00", "title": "ประชุม",
        "purpose": "teaching", "unit": str(flow["unit"].pk), "responsible_name": "ร.ท.ทดสอบ",
        "responsible_phone": "081", "attendees": "", "has_external_attendees": "False",
        "visibility": "normal", "action": "submit",
    })
    assert response.status_code == 200
    assert response.context["form"].has_more_data is True


# ---------- ผลการยื่น: ตราประทับครั้งเดียว + .ics ----------

def _submit(client, room, user, day, title="ประชุมเตรียมการฝึก"):
    return client.post(reverse("bookings:book_form", args=[room.code]), {
        "date": day.isoformat(), "start_time": "13:00", "end_time": "16:00", "title": title,
        "purpose": "teaching", "unit": str(user.unit_id), "responsible_name": "ร.ท.ทดสอบ",
        "responsible_phone": "081-111-1111", "attendees": "25", "has_external_attendees": "False",
        "visibility": "normal", "action": "submit",
    })


def test_auto_approved_stamp_shown_once(client, flow):
    room = make_room("STAMP-A")
    day = next_monday()
    client.force_login(flow["user"])
    response = _submit(client, room, flow["user"], day)
    assert response.status_code == 302
    detail = client.get(response["Location"]).content.decode()
    assert 'class="stamp result-stamp stamp-approved"' in detail
    assert "อนุมัติ" in detail and "เพิ่มลงปฏิทิน" in detail
    again = client.get(response["Location"]).content.decode()
    assert "result-stamp" not in again
    assert "เพิ่มลงปฏิทิน (.ics)" in again  # ลิงก์ปฏิทินยังอยู่ในรายละเอียด


def test_pending_stamp_for_required_approval(client, flow):
    room = make_room("STAMP-P", policy=ResourceRule.ApprovalPolicy.REQUIRED)
    client.force_login(flow["user"])
    response = _submit(client, room, flow["user"], next_monday())
    detail = client.get(response["Location"]).content.decode()
    assert 'class="stamp result-stamp stamp-pending"' in detail
    assert "รอพิจารณา" in detail


def test_stamp_flag_does_not_leak_to_other_booking(client, flow):
    room = make_room("STAMP-X")
    day = next_monday()
    old = book(room, flow["user"], at(day, 8), at(day, 9))
    client.force_login(flow["user"])
    response = _submit(client, room, flow["user"], day)
    assert "result-stamp" not in client.get(reverse("bookings:booking_detail", args=[old.id])).content.decode()
    assert "result-stamp" in client.get(response["Location"]).content.decode()


def test_ics_content_uses_utc_and_escapes_text(flow):
    room = make_room("ICS-1")
    day = next_monday()
    booking = book(room, flow["user"], at(day, 9), at(day, 10, 30), title="ประชุม, วางแผน; ฝึก")
    text = booking_ics(booking, "http://sigroom.local/bookings/x/", now=at(day, 7))
    assert text.startswith("BEGIN:VCALENDAR\r\n")
    assert f"DTSTART:{day:%Y%m%d}T020000Z" in text  # 09:00 น. เวลาไทย = 02:00 UTC
    assert f"DTEND:{day:%Y%m%d}T033000Z" in text
    assert "ประชุม\\, วางแผน\\; ฝึก (ICS-1)" in text.replace("\r\n ", "")
    assert "STATUS:CONFIRMED" in text
    assert all(len(line.encode("utf-8")) <= 75 for line in text.split("\r\n"))


def test_ics_view_permission_and_headers(client, flow):
    room = make_room("ICS-2")
    booking = book(room, flow["user"], at(next_monday(), 9), at(next_monday(), 10))
    url = reverse("bookings:booking_ics", args=[booking.id])
    assert client.get(url).status_code == 302  # ต้องเข้าสู่ระบบ
    client.force_login(flow["other"])
    assert client.get(url).status_code == 403  # คนต่างหน่วย ไม่เห็นรายละเอียดเต็ม
    client.force_login(flow["user"])
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/calendar")
    assert "attachment;" in response["Content-Disposition"] and ".ics" in response["Content-Disposition"]
    assert f"UID:{booking.id}@sigroom" in response.content.decode()

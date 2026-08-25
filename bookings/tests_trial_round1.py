from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import Unit, User
from bookings.forms import BookingForm
from bookings.models import Booking, ReferenceValue
from bookings.services import frequent_values
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def trial_data():
    unit = Unit.objects.create(code="COMM", name="แผนกเดิม")
    user = User.objects.create_user(
        username="trial", email="trial@signalschool.ac.th", password="Password-2569",
        unit=unit, rank="ร.อ.", first_name="สมชาย", last_name="ใจดี", phone="0812345678",
    )
    room = Resource.objects.create(code="R-101", name="ห้องทดลอง", capacity=30)
    ResourceRule.objects.create(resource=room, service_start=time(7), service_end=time(21))
    return unit, user, room


def test_import_units_creates_parents_and_updates_without_duplicates(tmp_path):
    source = tmp_path / "units.csv"
    source.write_text("code,name,parent\nCHILD,หน่วยลูก,PARENT\nPARENT,หน่วยแม่,\n", encoding="utf-8-sig")
    call_command("import_units", str(source))
    assert Unit.objects.count() == 2
    assert Unit.objects.get(code="CHILD").parent.code == "PARENT"

    source.write_text("code,name,parent\nCHILD,หน่วยลูกชื่อใหม่,PARENT\nPARENT,หน่วยแม่,\n", encoding="utf-8-sig")
    call_command("import_units", str(source))
    assert Unit.objects.count() == 2
    assert Unit.objects.get(code="CHILD").name == "หน่วยลูกชื่อใหม่"


def test_frequent_values_reference_first_then_unique_recent_history(trial_data):
    unit, user, room = trial_data
    ReferenceValue.objects.create(field="title", value="วิชาอ้างอิง ก", order=2)
    ReferenceValue.objects.create(field="title", value="วิชาซ้ำ", order=1)
    start = timezone.now() + timedelta(days=3)
    for index, title in enumerate(("วิชาเก่า", "วิชาซ้ำ", "วิชาใหม่")):
        Booking.objects.create(
            room=room, requester=user, unit=unit, responsible_name=user.display_name,
            responsible_phone=user.phone, title=title,
            start_at=start + timedelta(hours=index), end_at=start + timedelta(hours=index + 1),
        )
    values = frequent_values(unit, "title")
    assert values[:2] == ["วิชาซ้ำ", "วิชาอ้างอิง ก"]
    assert values.count("วิชาซ้ำ") == 1
    assert values[2:] == ["วิชาใหม่", "วิชาเก่า"]


def test_import_reference_is_idempotent(tmp_path):
    source = tmp_path / "titles.txt"
    source.write_text(" วิชา ก \nวิชา ข\nวิชา ก\n\n", encoding="utf-8")
    call_command("import_reference", "title", str(source))
    call_command("import_reference", "title", str(source))
    assert list(ReferenceValue.objects.filter(field="title").order_by("value").values_list("value", flat=True)) == ["วิชา ก", "วิชา ข"]


def test_room_list_heading_reports_available_count(trial_data):
    _, _, room = trial_data
    result = SimpleNamespace(room=room, approval_label="อนุมัติอัตโนมัติ", capacity_warning=False)
    html = render_to_string(
        "bookings/partials/room_list.html",
        {"searched": True, "error": "", "available": [result], "unavailable": [], "query_string": ""},
    )
    assert "พบ 1 ห้องว่าง" in html


def test_booking_form_prefills_responsible_fields_from_user(trial_data):
    unit, user, room = trial_data
    form = BookingForm(user=user, room=room, instance=Booking(room=room, requester=user, unit=unit))
    assert form.initial["unit"] == unit.pk
    assert form.initial["responsible_name"] == user.display_name
    assert form.initial["responsible_phone"] == user.phone


def test_booking_form_more_section_opens_for_error(trial_data):
    unit, user, room = trial_data
    tomorrow = timezone.localdate() + timedelta(days=2)
    data = {
        "date": tomorrow.isoformat(), "start_time": "09:00", "end_time": "10:00",
        "title": "ทดสอบ", "purpose": Booking.Purpose.TEACHING, "unit": str(unit.pk),
        "responsible_name": user.display_name, "responsible_phone": user.phone, "attendees": "10",
        "has_external_attendees": "True", "external_attendees_note": "", "visibility": Booking.Visibility.NORMAL,
    }
    form = BookingForm(data, user=user, room=room, instance=Booking(room=room, requester=user, unit=unit))
    assert not form.is_valid()
    assert "external_attendees_note" in form.errors
    assert form.has_more_data is True


def test_allowed_fields_partial_renders_without_keyerror(trial_data):
    unit, user, room = trial_data
    booking = Booking.objects.create(
        room=room, requester=user, unit=unit, responsible_name=user.display_name, responsible_phone=user.phone,
        title="เดิม", start_at=timezone.now() + timedelta(days=2), end_at=timezone.now() + timedelta(days=2, hours=1),
    )
    form = BookingForm(user=user, room=room, instance=booking, allowed_fields={"title"})
    html = render_to_string(
        "bookings/partials/booking_fields.html",
        {"form": form, "room": room, "submit_label": "บันทึก", "show_draft": False},
    )
    assert "ชื่อกิจกรรม / วิชา" in html
    assert "ผู้รับผิดชอบ" not in html

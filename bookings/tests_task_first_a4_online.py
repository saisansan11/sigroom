from datetime import datetime, time, timedelta

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from audit.models import AuditLog
from bookings.models import Booking, Course, CourseRun
from bookings.online_teaching import ONLINE_TEACHER_GROUP, ONLINE_TEACHING_ROOM_CODES
from bookings.online_teaching_services import create_online_teaching_booking, suggest_online_rooms
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def a4_setup():
    edu = Unit.objects.create(code="A4-EDU", name="กองการศึกษา")
    other = Unit.objects.create(code="A4-OTHER", name="หน่วยอื่น")
    teacher = User.objects.create_user(
        username="a4-teacher",
        email="a4-teacher@signalschool.ac.th",
        password="Password-2569",
        first_name="ครู",
        last_name="เอสี่",
        rank="ร.อ.",
        phone="0812345678",
        unit=edu,
    )
    non_teacher = User.objects.create_user(
        username="a4-user",
        email="a4-user@signalschool.ac.th",
        password="Password-2569",
        phone="0890000000",
        unit=other,
    )
    teacher_group = Group.objects.create(name=ONLINE_TEACHER_GROUP)
    teacher.groups.add(teacher_group)

    rooms = []
    for index, code in enumerate(ONLINE_TEACHING_ROOM_CODES, 1):
        room = Resource.objects.create(
            code=code,
            name=f"ห้องสอนออนไลน์ {index}",
            resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.ONLINE,
            building="อาคาร บก.กศ.",
            floor="1",
            capacity=5,
            owner_unit=edu,
        )
        ResourceRule.objects.create(
            resource=room,
            approval_policy=ResourceRule.ApprovalPolicy.AUTO,
            service_start=time(7, 30),
            service_end=time(17, 0),
            min_duration_min=30,
            max_duration_min=240,
            buffer_after_min=15,
        )
        rooms.append(room)

    course = Course.objects.create(code="a4-course", name="หลักสูตร A4")
    today = timezone.localdate()
    run = CourseRun.objects.create(
        course=course,
        slug="a4-course-1",
        run_number=1,
        start_date=today - timedelta(days=2),
        end_date=today + timedelta(days=60),
    )
    return {"edu": edu, "other": other, "teacher": teacher, "non_teacher": non_teacher, "rooms": rooms, "run": run}


def _range(days=3, start=time(9), end=time(10)):
    day = timezone.localdate() + timedelta(days=days)
    zone = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(day, start), zone),
        timezone.make_aware(datetime.combine(day, end), zone),
    )


def _quick_payload(room, run, start_at, end_at, **extra):
    payload = {
        "room": str(room.pk),
        "start_at": start_at.isoformat(),
        "end_at": end_at.isoformat(),
        "course_run": str(run.pk),
        "purpose": Booking.Purpose.TEACHING,
        "return_query": urlencode_selection(start_at, end_at, run),
    }
    payload.update(extra)
    return payload


def urlencode_selection(start_at, end_at, run):
    from urllib.parse import urlencode

    local = timezone.localtime(start_at)
    minutes = int((end_at - start_at).total_seconds() // 60)
    return urlencode(
        {
            "day": local.date().isoformat(),
            "start": local.strftime("%H:%M"),
            "dur": str(minutes),
            "course_run": str(run.pk),
            "purpose": Booking.Purpose.TEACHING,
        }
    )


def test_results_skip_busy_room_and_offer_free_rooms(client, a4_setup):
    start_at, end_at = _range()
    create_online_teaching_booking(
        user=a4_setup["teacher"],
        room=a4_setup["rooms"][0],
        start_at=start_at,
        end_at=end_at,
        course_run=a4_setup["run"],
        purpose=Booking.Purpose.TEACHING,
    )
    client.force_login(a4_setup["teacher"])
    response = client.get(
        reverse("bookings:online_teaching_home"),
        {
            "day": timezone.localdate(start_at).isoformat(),
            "start": "09:00",
            "dur": "60",
            "course_run": str(a4_setup["run"].pk),
        },
    )
    assert response.status_code == 200
    offered = [room.code for room in response.context["rooms"]]
    assert a4_setup["rooms"][0].code not in offered
    assert a4_setup["rooms"][1].code in offered


def test_quick_confirm_creates_one_approved_booking_and_audit(client, a4_setup):
    start_at, end_at = _range()
    client.force_login(a4_setup["teacher"])
    response = client.post(
        reverse("bookings:online_teaching_quick_book"),
        _quick_payload(a4_setup["rooms"][1], a4_setup["run"], start_at, end_at),
    )
    assert response.status_code == 302
    booking = Booking.objects.get()
    assert response.url == reverse("bookings:booking_pass", args=[booking.pk])
    assert booking.room_id == a4_setup["rooms"][1].pk
    assert booking.request_status == Booking.RequestStatus.APPROVED
    assert AuditLog.objects.filter(
        action="online_teaching_booked", entity="bookings.booking", entity_id=str(booking.pk)
    ).exists()


def test_duplicate_quick_confirm_does_not_create_second_booking(client, a4_setup):
    start_at, end_at = _range()
    client.force_login(a4_setup["teacher"])
    payload = _quick_payload(a4_setup["rooms"][0], a4_setup["run"], start_at, end_at)
    first = client.post(reverse("bookings:online_teaching_quick_book"), payload)
    assert first.status_code == 302
    second = client.post(reverse("bookings:online_teaching_quick_book"), payload, follow=True)
    assert second.status_code == 200
    assert Booking.objects.count() == 1
    assert "ห้องนี้เพิ่งถูกจอง กรุณาเลือกห้องอื่น" in second.content.decode()


def test_quick_post_rejects_non_online_room_tamper(client, a4_setup):
    start_at, end_at = _range()
    meeting = Resource.objects.create(
        code="A4-MEET",
        name="ห้องประชุม",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.MEETING,
        owner_unit=a4_setup["edu"],
    )
    ResourceRule.objects.create(resource=meeting, approval_policy=ResourceRule.ApprovalPolicy.AUTO)
    client.force_login(a4_setup["teacher"])
    response = client.post(
        reverse("bookings:online_teaching_quick_book"),
        _quick_payload(meeting, a4_setup["run"], start_at, end_at),
        follow=True,
    )
    assert response.status_code == 200
    assert not Booking.objects.exists()
    assert "ห้องที่เลือกไม่ใช่ห้องสอนออนไลน์" in response.content.decode()


def test_am_duration_uses_first_preset_not_requested_start(client, a4_setup):
    start_at, _ = _range()
    client.force_login(a4_setup["teacher"])
    response = client.get(
        reverse("bookings:online_teaching_home"),
        {
            "day": timezone.localdate(start_at).isoformat(),
            "start": "15:00",
            "dur": "am",
            "course_run": str(a4_setup["run"].pk),
        },
    )
    selection = response.context["selection"]
    assert timezone.localtime(selection["start"]).strftime("%H:%M") == "08:00"
    assert timezone.localtime(selection["end"]).strftime("%H:%M") == "12:00"


def test_no_rooms_returns_at_most_three_nearby_future_slots(a4_setup):
    start_at, end_at = _range()
    for room in a4_setup["rooms"]:
        create_online_teaching_booking(
            user=a4_setup["teacher"],
            room=room,
            start_at=start_at,
            end_at=end_at,
            course_run=a4_setup["run"],
            purpose=Booking.Purpose.TEACHING,
        )
    rooms, alternatives = suggest_online_rooms(
        user=a4_setup["teacher"], start_at=start_at, end_at=end_at
    )
    assert rooms == []
    assert len(alternatives) <= 3
    assert all(item["start_at"] >= timezone.now() for item in alternatives)
    assert all(timezone.localdate(item["start_at"]) == timezone.localdate(start_at) for item in alternatives)


def test_missing_phone_shows_profile_box_then_saves_and_enables_confirm(client, a4_setup):
    teacher = a4_setup["teacher"]
    teacher.phone = ""
    teacher.save(update_fields=["phone"])
    start_at, end_at = _range()
    query = urlencode_selection(start_at, end_at, a4_setup["run"])
    client.force_login(teacher)

    before = client.get(reverse("bookings:online_teaching_home") + "?" + query)
    html = before.content.decode()
    assert "เติมข้อมูลสำหรับการจอง" in html
    assert "ยืนยันจอง" not in html

    response = client.post(
        reverse("bookings:online_teaching_profile"),
        {"phone": "081-111-2233", "unit": str(a4_setup["other"].pk), "return_query": query},
        follow=True,
    )
    teacher.refresh_from_db()
    assert teacher.phone == "0811112233"
    assert teacher.unit_id == a4_setup["edu"].pk
    assert "ยืนยันจอง" in response.content.decode()
    assert AuditLog.objects.filter(action="contact_profile_completed", entity_id=str(teacher.pk)).exists()


def test_profile_post_never_replaces_existing_unit(client, a4_setup):
    teacher = a4_setup["teacher"]
    original_unit = teacher.unit_id
    client.force_login(teacher)
    response = client.post(
        reverse("bookings:online_teaching_profile"),
        {"unit": str(a4_setup["other"].pk), "phone": "0999999999"},
    )
    assert response.status_code == 302
    teacher.refresh_from_db()
    assert teacher.unit_id == original_unit
    assert teacher.phone == "0812345678"


def test_non_teacher_gets_explanation_but_all_online_posts_stay_forbidden(client, a4_setup):
    start_at, end_at = _range()
    client.force_login(a4_setup["non_teacher"])
    page = client.get(reverse("bookings:online_teaching_home"))
    assert page.status_code == 200
    assert "บัญชีนี้ยังไม่มีสิทธิ์จองห้องสอนออนไลน์" in page.content.decode()

    quick = client.post(
        reverse("bookings:online_teaching_quick_book"),
        _quick_payload(a4_setup["rooms"][0], a4_setup["run"], start_at, end_at),
    )
    profile = client.post(reverse("bookings:online_teaching_profile"), {"phone": "0811111111"})
    assert quick.status_code == 403
    assert profile.status_code == 403


def test_task_first_journey_gateway_online_quick_confirm(client, a4_setup):
    start_at, end_at = _range(days=4)
    client.force_login(a4_setup["teacher"])
    gateway = client.get(reverse("bookings:lodging_about"))
    assert gateway.status_code == 200
    assert reverse("bookings:online_teaching_home") in gateway.content.decode()

    online = client.get(
        reverse("bookings:online_teaching_home"),
        {
            "day": timezone.localdate(start_at).isoformat(),
            "start": timezone.localtime(start_at).strftime("%H:%M"),
            "dur": "60",
            "course_run": str(a4_setup["run"].pk),
        },
    )
    assert online.status_code == 200
    room = online.context["rooms"][0]
    confirmed = client.post(
        reverse("bookings:online_teaching_quick_book"),
        _quick_payload(room, a4_setup["run"], start_at, end_at),
    )
    assert confirmed.status_code == 302
    assert confirmed.url == reverse("bookings:booking_pass", args=[Booking.objects.get(room=room, requester=a4_setup["teacher"]).pk])
    assert Booking.objects.filter(room=room, requester=a4_setup["teacher"]).count() == 1


def test_filter_is_one_tap_chips_without_typing_or_apply_buttons(client, a4_setup):
    client.force_login(a4_setup["teacher"])
    html = client.get(reverse("bookings:online_teaching_home")).content.decode()
    assert 'name="start" value="07:00"' in html
    assert 'name="start" value="17:30"' in html
    assert 'name="start" value="18:00"' not in html
    assert 'hx-trigger="change"' in html
    assert "ใช้วันที่นี้" not in html
    assert "ใช้เวลานี้" not in html
    assert 'id="online-custom-date"' not in html
    assert "รองรับ" not in html


def test_calendar_offers_only_bookable_days_and_marks_selected_day(client, a4_setup):
    today = timezone.localdate()
    far_day = today + timedelta(days=20)
    client.force_login(a4_setup["teacher"])
    response = client.get(
        reverse("bookings:online_teaching_home"),
        {"day": far_day.isoformat(), "start": "09:00", "dur": "60"},
    )
    calendar = response.context["calendar"]
    days = [day for week in calendar["weeks"] for day in week]
    assert str(far_day.year + 543) in calendar["title"]
    assert [day["value"] for day in days if day["selected"]] == [far_day.isoformat()]
    assert all(day["date"] >= today for day in days if day["enabled"])
    assert response.context["calendar_open"] is True
    assert f'name="day" value="{far_day.isoformat()}" checked' in response.content.decode()


def test_htmx_swaps_only_results_or_only_calendar(client, a4_setup):
    client.force_login(a4_setup["teacher"])
    url = reverse("bookings:online_teaching_home")
    results = client.get(url, {"start": "09:00", "dur": "60"}, HTTP_HX_REQUEST="true", HTTP_HX_TARGET="online-results")
    assert results.content.decode().lstrip().startswith('<div id="online-results"')
    next_month = (timezone.localdate().replace(day=1) + timedelta(days=31)).replace(day=1)
    calendar = client.get(
        url,
        {"cal": f"{next_month.year:04d}-{next_month.month:02d}"},
        HTTP_HX_REQUEST="true",
        HTTP_HX_TARGET="online-calendar",
    )
    html = calendar.content.decode()
    assert html.lstrip().startswith('<div id="online-calendar"')
    assert str(next_month.year + 543) in html
    assert 'id="online-results"' not in html


def test_teacher_lands_on_online_booking_after_login_but_superuser_keeps_gateway(client, a4_setup):
    client.force_login(a4_setup["teacher"])
    assert client.get(reverse("bookings:role_home")).url == reverse("bookings:online_teaching_home")

    admin = User.objects.create_superuser(username="a4-admin", email="a4-admin@signalschool.ac.th", password="Password-2569")
    client.force_login(admin)
    assert client.get(reverse("bookings:role_home")).url == reverse("bookings:lodging_about")

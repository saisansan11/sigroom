from datetime import datetime, time, timedelta
from io import StringIO

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking, Course, CourseRun, ReferenceValue
from bookings.lodging_models import CourseLodgingCohort
from bookings.online_teaching import (
    ONLINE_TEACHER_GROUP,
    ONLINE_TEACHING_ROOM_CODES,
    can_book_online_teaching,
)
from bookings.services import submit_booking
from resources.models import Blackout, Resource, ResourceRule

pytestmark = pytest.mark.django_db


def _future_day(days=3):
    return timezone.localdate() + timedelta(days=days)


def _post_payload(course_run, *, day=None, start="09:00", end="10:00", purpose=Booking.Purpose.TEACHING, **extra):
    payload = {
        "date": (day or _future_day()).isoformat(),
        "start_time": start,
        "end_time": end,
        "course_run": str(course_run.pk),
        "purpose": purpose,
        "action": "book",
    }
    payload.update(extra)
    return payload


@pytest.fixture
def online_e_setup():
    edu = Unit.objects.create(code="EDU", name="กองการศึกษา")
    other_unit = Unit.objects.create(code="E-OTHER", name="หน่วยอื่น")
    teacher = User.objects.create_user(
        username="e-teacher",
        email="e-teacher@signalschool.ac.th",
        password="Password-2569",
        first_name="ครู",
        last_name="ทดสอบ",
        rank="ร.อ.",
        phone="0812345678",
        unit=edu,
    )
    non_teacher = User.objects.create_user(
        username="e-user",
        email="e-user@signalschool.ac.th",
        password="Password-2569",
        unit=other_unit,
        phone="0823456789",
    )
    group = Group.objects.create(name=ONLINE_TEACHER_GROUP)
    teacher.groups.add(group)

    rooms = []
    for idx, code in enumerate(ONLINE_TEACHING_ROOM_CODES, 1):
        room = Resource.objects.create(
            code=code,
            name=f"ห้องสอนออนไลน์ {idx}",
            resource_type=Resource.Type.ROOM,
            room_category=Resource.Category.ONLINE,
            building="อาคาร บก.กศ.",
            floor="1",
            capacity=5,
            owner_unit=edu,
            fixed_equipment="กล้อง\nไมโครโฟน\nไฟสตูดิโอ\nจอเขียว",
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

    course_a = Course.objects.create(code="test-a", name="หลักสูตรทดสอบ ก")
    course_b = Course.objects.create(code="test-b", name="หลักสูตรทดสอบ ข")
    today = timezone.localdate()
    courses = [
        CourseRun.objects.create(
            course=course_a,
            slug="test-a-1",
            run_number=1,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=60),
        ),
        CourseRun.objects.create(
            course=course_b,
            slug="test-b-3",
            run_number=3,
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=90),
        ),
    ]
    for order, run in enumerate(courses, 1):
        ReferenceValue.objects.create(field="attendee_level", value=run.display_name, order=order)

    return {
        "edu": edu,
        "other_unit": other_unit,
        "teacher": teacher,
        "non_teacher": non_teacher,
        "rooms": rooms,
        "courses": courses,
    }


def test_teacher_role_is_group_backed_and_superuser_supported(online_e_setup):
    assert can_book_online_teaching(online_e_setup["teacher"]) is True
    assert can_book_online_teaching(online_e_setup["non_teacher"]) is False
    superuser = User.objects.create_superuser(
        username="e-admin", email="e-admin@signalschool.ac.th", password="Password-2569"
    )
    assert can_book_online_teaching(superuser) is True


def test_online_hub_requires_login_and_teacher_role(client, online_e_setup):
    url = reverse("bookings:online_teaching_home")
    anonymous = client.get(url)
    assert anonymous.status_code == 302
    assert "/accounts/login/" in anonymous.url

    client.force_login(online_e_setup["non_teacher"])
    assert client.get(url).status_code == 403

    client.force_login(online_e_setup["teacher"])
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    for code in ONLINE_TEACHING_ROOM_CODES:
        assert code in html
    assert html.count("ดูรายละเอียดและจอง") == 3


def test_online_form_is_focused_and_course_is_strict_dropdown(client, online_e_setup):
    teacher = online_e_setup["teacher"]
    room = online_e_setup["rooms"][0]
    client.force_login(teacher)
    response = client.get(reverse("bookings:online_teaching_book", args=[room.code]))
    assert response.status_code == 200
    form = response.context["form"]
    assert set(form.fields) == {"date", "start_time", "end_time", "course_run", "purpose"}
    assert list(form.fields["course_run"].queryset) == online_e_setup["courses"]
    assert "unit" not in form.fields
    assert "responsible_name" not in form.fields
    assert "title" not in form.fields


def test_invalid_or_inactive_course_is_rejected_server_side(client, online_e_setup):
    teacher = online_e_setup["teacher"]
    room = online_e_setup["rooms"][0]
    client.force_login(teacher)
    url = reverse("bookings:online_teaching_book", args=[room.code])

    invalid_payload = _post_payload(online_e_setup["courses"][0])
    invalid_payload["course_run"] = "00000000-0000-0000-0000-000000000000"
    invalid = client.post(url, invalid_payload)
    assert invalid.status_code == 200
    assert not Booking.objects.exists()

    online_e_setup["courses"][0].is_active = False
    online_e_setup["courses"][0].save(update_fields=["is_active"])
    inactive = client.post(url, _post_payload(online_e_setup["courses"][0]))
    assert inactive.status_code == 200
    assert not Booking.objects.exists()


def test_teacher_booking_auto_approves_and_client_cannot_spoof_owner_or_unit(client, online_e_setup):
    teacher = online_e_setup["teacher"]
    room = online_e_setup["rooms"][0]
    course = online_e_setup["courses"][0]
    client.force_login(teacher)
    response = client.post(
        reverse("bookings:online_teaching_book", args=[room.code]),
        _post_payload(
            course,
            requester=str(online_e_setup["non_teacher"].pk),
            unit=str(online_e_setup["other_unit"].pk),
            responsible_name="ผู้ปลอม",
            title="ชื่อปลอม",
            request_status=Booking.RequestStatus.APPROVED,
        ),
    )
    assert response.status_code == 302
    booking = Booking.objects.get(room=room)
    assert booking.requester_id == teacher.pk
    assert booking.unit_id == teacher.unit_id
    assert booking.responsible_name == teacher.display_name
    assert booking.responsible_phone == teacher.phone
    assert booking.course_run_id == course.pk
    assert booking.title == course.display_name
    assert booking.attendee_level == course.display_name
    assert booking.request_status == Booking.RequestStatus.APPROVED
    assert booking.has_external_attendees is False
    assert booking.holds.filter(released_at__isnull=True).exists()


def test_non_teacher_direct_online_book_url_is_forbidden(client, online_e_setup):
    room = online_e_setup["rooms"][0]
    client.force_login(online_e_setup["non_teacher"])
    url = reverse("bookings:online_teaching_book", args=[room.code])
    assert client.get(url).status_code == 403
    assert client.post(url, _post_payload(online_e_setup["courses"][0])).status_code == 403


def test_submit_booking_service_rejects_non_teacher_for_online_room(online_e_setup):
    user = online_e_setup["non_teacher"]
    room = online_e_setup["rooms"][0]
    day = _future_day()
    zone = timezone.get_current_timezone()
    booking = Booking(
        room=room,
        requester=user,
        unit=user.unit,
        responsible_name=user.display_name,
        responsible_phone=user.phone,
        title=online_e_setup["courses"][0].display_name,
        attendee_level=online_e_setup["courses"][0].display_name,
        start_at=timezone.make_aware(datetime.combine(day, time(9)), zone),
        end_at=timezone.make_aware(datetime.combine(day, time(10)), zone),
    )
    booking.save()
    from django.core.exceptions import ValidationError
    with pytest.raises(ValidationError, match="เฉพาะครู"):
        submit_booking(booking)
    assert not booking.holds.exists()


def test_generic_online_booking_url_cannot_bypass_focused_workflow(client, online_e_setup):
    room = online_e_setup["rooms"][0]
    teacher = online_e_setup["teacher"]
    client.force_login(teacher)
    generic = reverse("bookings:book_form", args=[room.code])
    get_response = client.get(generic)
    assert get_response.status_code == 302
    assert get_response.url == reverse("bookings:online_teaching_book", args=[room.code])
    post_response = client.post(generic, {"title": "free text"})
    assert post_response.status_code == 403
    assert not Booking.objects.exists()


def test_unapproved_online_resource_code_is_not_bookable_through_focused_workflow(client, online_e_setup):
    extra = Resource.objects.create(
        code="ONLINE-EXTRA",
        name="ห้องออนไลน์นอก allowlist",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.ONLINE,
        owner_unit=online_e_setup["edu"],
    )
    ResourceRule.objects.create(resource=extra, approval_policy=ResourceRule.ApprovalPolicy.AUTO)
    client.force_login(online_e_setup["teacher"])
    assert client.get(reverse("bookings:online_teaching_book", args=[extra.code])).status_code == 404


def test_required_policy_fails_closed_in_teacher_workflow(client, online_e_setup):
    room = online_e_setup["rooms"][0]
    room.rule.approval_policy = ResourceRule.ApprovalPolicy.REQUIRED
    room.rule.save(update_fields=["approval_policy"])
    client.force_login(online_e_setup["teacher"])
    assert client.get(reverse("bookings:online_teaching_book", args=[room.code])).status_code == 403


def test_conflict_and_blackout_use_existing_booking_core_guards(client, online_e_setup):
    teacher = online_e_setup["teacher"]
    room = online_e_setup["rooms"][0]
    course = online_e_setup["courses"][0]
    day = _future_day()
    zone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time(9)), zone)
    end = timezone.make_aware(datetime.combine(day, time(10)), zone)
    blocker = Booking.objects.create(
        room=room,
        requester=teacher,
        unit=teacher.unit,
        responsible_name=teacher.display_name,
        responsible_phone=teacher.phone,
        title="รายการเดิม",
        start_at=start,
        end_at=end,
    )
    submit_booking(blocker)

    client.force_login(teacher)
    url = reverse("bookings:online_teaching_book", args=[room.code])
    conflict = client.post(url, _post_payload(course, day=day, start="09:30", end="10:30"))
    assert conflict.status_code == 200
    assert Booking.objects.count() == 1
    assert "ไม่ว่าง" in conflict.content.decode()

    other_room = online_e_setup["rooms"][1]
    Blackout.objects.create(
        title="ทดสอบงดใช้",
        start_at=start,
        end_at=end,
        scope=Blackout.Scope.ROOMS,
        created_by=teacher,
    ).rooms.add(other_room)
    blackout = client.post(
        reverse("bookings:online_teaching_book", args=[other_room.code]),
        _post_payload(course, day=day),
    )
    assert blackout.status_code == 200
    assert Booking.objects.filter(room=other_room).count() == 0
    assert "กิจกรรมส่วนกลาง" in blackout.content.decode() or "งด" in blackout.content.decode()


def test_online_booking_edit_does_not_allow_course_or_owner_rewrite(client, online_e_setup):
    teacher = online_e_setup["teacher"]
    room = online_e_setup["rooms"][0]
    course = online_e_setup["courses"][0]
    client.force_login(teacher)
    client.post(reverse("bookings:online_teaching_book", args=[room.code]), _post_payload(course))
    booking = Booking.objects.get(room=room)

    edit = client.get(reverse("bookings:booking_edit", args=[booking.pk]))
    assert edit.status_code == 200
    assert set(edit.context["form"].fields).issubset({"online_meeting_url", "attendees", "note"})

    client.post(
        reverse("bookings:booking_edit", args=[booking.pk]),
        {
            "title": "หลักสูตรปลอม",
            "attendee_level": "หลักสูตรปลอม",
            "responsible_name": "เปลี่ยนเจ้าของ",
            "online_meeting_url": "https://meet.google.com/abc-defg-hij",
        },
    )
    booking.refresh_from_db()
    assert booking.course_run_id == course.pk
    assert booking.title == course.display_name
    assert booking.attendee_level == course.display_name
    assert booking.responsible_name == teacher.display_name


def test_other_teacher_cannot_edit_or_cancel_owners_booking(client, online_e_setup):
    owner = online_e_setup["teacher"]
    room = online_e_setup["rooms"][0]
    client.force_login(owner)
    client.post(
        reverse("bookings:online_teaching_book", args=[room.code]),
        _post_payload(online_e_setup["courses"][0]),
    )
    booking = Booking.objects.get(room=room)

    other = User.objects.create_user(
        username="e-other-teacher",
        email="e-other-teacher@signalschool.ac.th",
        password="Password-2569",
        unit=online_e_setup["edu"],
        phone="0834567890",
    )
    other.groups.add(Group.objects.get(name=ONLINE_TEACHER_GROUP))
    client.force_login(other)
    assert client.get(reverse("bookings:booking_edit", args=[booking.pk])).status_code == 403
    cancel = client.post(reverse("bookings:booking_cancel", args=[booking.pk]))
    assert cancel.status_code == 302
    booking.refresh_from_db()
    assert booking.request_status == Booking.RequestStatus.APPROVED


def test_online_booking_cannot_use_generic_amendment_path(client, online_e_setup):
    teacher = online_e_setup["teacher"]
    room = online_e_setup["rooms"][0]
    client.force_login(teacher)
    client.post(
        reverse("bookings:online_teaching_book", args=[room.code]),
        _post_payload(online_e_setup["courses"][0]),
    )
    booking = Booking.objects.get(room=room)
    assert client.get(reverse("bookings:booking_amend", args=[booking.pk])).status_code == 403


def test_seed_online_teaching_is_idempotent_and_can_assign_teacher():
    edu = Unit.objects.create(code="EDU", name="กองการศึกษา")
    teacher = User.objects.create_user(
        username="seed-teacher",
        email="seed-teacher@signalschool.ac.th",
        password="Password-2569",
        unit=edu,
    )
    output = StringIO()
    call_command("seed_online_teaching", teacher=teacher.username, stdout=output)
    call_command("seed_online_teaching", teacher=teacher.username, stdout=output)

    assert set(
        Resource.objects.filter(room_category=Resource.Category.ONLINE).values_list("code", flat=True)
    ) == set(ONLINE_TEACHING_ROOM_CODES)
    assert Resource.objects.filter(room_category=Resource.Category.ONLINE).count() == 3
    assert all(
        room.rule.approval_policy == ResourceRule.ApprovalPolicy.AUTO
        for room in Resource.objects.filter(code__in=ONLINE_TEACHING_ROOM_CODES).select_related("rule")
    )
    teacher.refresh_from_db()
    assert teacher.groups.filter(name=ONLINE_TEACHER_GROUP).exists()
    assert CourseRun.objects.filter(is_active=True).count() >= 14
    assert ReferenceValue.objects.filter(field="attendee_level", is_active=True).count() >= 14


def test_seed_online_teaching_fails_closed_on_conflicting_reserved_code():
    edu = Unit.objects.create(code="EDU", name="กองการศึกษา")
    Resource.objects.create(
        code="STU-ONLINE-1",
        name="ห้องคนละประเภท",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.MEETING,
        owner_unit=edu,
    )
    with pytest.raises(CommandError, match="ไม่ใช่ห้องสอนออนไลน์"):
        call_command("seed_online_teaching", stdout=StringIO())
    assert Resource.objects.filter(code="STU-ONLINE-2").count() == 0



def test_course_catalog_opens_next_run_without_retyping_course_name(client):
    manager = User.objects.create_superuser(
        username="course-manager",
        email="course-manager@signalschool.ac.th",
        password="Password-2569",
    )
    course = Course.objects.create(
        code="nns",
        name="นนส.ทบ. 1 ปี 6 เดือน เหล่า ส.(ระยะเวลา 8 เดือน)",
        include_year_in_label=True,
    )
    CourseRun.objects.create(
        course=course,
        slug="nns-29-68",
        run_number=29,
        year_code="68",
        start_date=timezone.localdate() - timedelta(days=100),
        end_date=timezone.localdate() - timedelta(days=10),
    )
    CourseRun.objects.create(
        course=course,
        slug="nns-30-69",
        run_number=30,
        year_code="69",
        start_date=timezone.localdate() + timedelta(days=30),
        end_date=timezone.localdate() + timedelta(days=120),
    )

    client.force_login(manager)
    url = reverse("bookings:course_catalog_manage")
    page = client.get(url)
    assert page.status_code == 200
    html = page.content.decode()
    assert "เปิดรุ่นถัดไป" in html
    assert "รุ่นที่ 31/70" in html

    start = timezone.localdate() + timedelta(days=180)
    end = start + timedelta(days=90)
    created = client.post(
        url,
        {
            "course_id": str(course.pk),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert created.status_code == 302
    run = CourseRun.objects.get(slug="nns-31-70")
    assert run.course_id == course.pk
    assert run.run_number == 31
    assert run.year_code == "70"
    assert run.display_name.endswith("รุ่นที่ 31/70")


def test_lodging_create_can_reuse_course_run_and_dates_without_title_typing(client):
    manager = User.objects.create_superuser(
        username="lodging-course-manager",
        email="lodging-course-manager@signalschool.ac.th",
        password="Password-2569",
    )
    unit = Unit.objects.create(code="LODGE", name="หน่วยที่พัก")
    manager.unit = unit
    manager.save(update_fields=["unit"])
    course = Course.objects.create(code="easy-course", name="หลักสูตรใช้งานง่าย")
    start = timezone.localdate() + timedelta(days=20)
    end = start + timedelta(days=30)
    run = CourseRun.objects.create(
        course=course,
        slug="easy-course-7",
        run_number=7,
        start_date=start,
        end_date=end,
    )
    room = Resource.objects.create(
        code="DORM-EASY-1",
        name="ห้องพักทดสอบ",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        owner_unit=unit,
        status=Resource.Status.ACTIVE,
    )

    client.force_login(manager)
    page = client.get(reverse("bookings:lodging_manage"))
    assert page.status_code == 200
    html = page.content.decode()
    assert 'name="course_run"' in html
    assert 'name="title"' not in html

    created = client.post(
        reverse("bookings:lodging_manage"),
        {
            "course_run": str(run.pk),
            "beds_per_room": "4",
            "rooms": [str(room.pk)],
            "publication": "closed",
        },
    )
    assert created.status_code == 302
    cohort = CourseLodgingCohort.objects.get(slug=run.slug)
    assert cohort.course_run_id == run.pk
    assert cohort.title == run.display_name
    assert cohort.check_in_date == run.start_date
    assert cohort.check_out_date == run.end_date

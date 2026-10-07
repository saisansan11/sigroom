"""UX-1 Task-First Shell & Home automated test suite."""
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort
from bookings.models import Booking
from resources.models import Resource, ResourceApprover, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def ux1_data():
    hq = Unit.objects.create(code="HQ-UX1", name="กองบัญชาการ UX1")
    edu = Unit.objects.create(code="EDU-UX1", name="กองการศึกษา UX1", parent=hq)

    normal_user = User.objects.create_user(
        username="normal_user",
        email="normal_user@signalschool.ac.th",
        password="Password-2569",
        unit=edu,
    )
    approver_user = User.objects.create_user(
        username="approver_user",
        email="approver_user@signalschool.ac.th",
        password="Password-2569",
        unit=hq,
    )
    custodian_user = User.objects.create_user(
        username="custodian_user",
        email="custodian_user@signalschool.ac.th",
        password="Password-2569",
        unit=edu,
    )
    supervisor_user = User.objects.create_user(
        username="supervisor_user",
        email="supervisor_user@signalschool.ac.th",
        password="Password-2569",
        unit=edu,
    )

    room = Resource.objects.create(
        code="UX1-101",
        name="ห้องเรียน UX1",
        building="อาคารทดสอบ UX1",
        floor=1,
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.CLASSROOM,
        capacity=30,
    )
    ResourceRule.objects.create(resource=room)
    ResourceApprover.objects.create(resource=room, user=approver_user, is_primary=True)
    room.custodians.add(custodian_user)

    dorm = Resource.objects.create(
        code="UX1-DORM",
        name="ห้องพัก UX1",
        building="อาคารนอน UX1",
        floor=1,
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
    )
    ResourceRule.objects.create(resource=dorm)

    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรทดสอบ UX1",
        slug="ux1-course",
        supervisor=supervisor_user,
        unit=edu,
        check_in_date=today,
        check_out_date=today + timedelta(days=7),
        beds_per_room=4,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    cohort.rooms.add(dorm)

    return {
        "normal_user": normal_user,
        "approver_user": approver_user,
        "custodian_user": custodian_user,
        "supervisor_user": supervisor_user,
        "room": room,
        "dorm": dorm,
        "cohort": cohort,
        "unit": edu,
    }


def _header_html(html: str) -> str:
    start = html.find("<header")
    end = html.find("</header>")
    return html[start:end] if start != -1 and end != -1 else html


def test_guest_navigation_is_simple(client):
    """Guest sees simple, clean navigation without authenticated clutter."""
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    header = _header_html(resp.content.decode())

    # PR-2: calendar ที่ไม่มี category ไม่สังกัดบริการ เมนูจึงเหลือแบรนด์และเข้าสู่ระบบ
    assert resp.context["nav_service"] is None
    assert f'class="brand" href="{reverse("bookings:lodging_about")}"' in header
    assert "สถานะห้องวันนี้" not in header
    assert "จองห้องพัก" not in header
    assert "เข้าสู่ระบบ" in header

    # Guest header must NOT see user or operational nav
    assert "การจองของฉัน" not in header
    assert "งานปฏิบัติการ" not in header
    assert "รออนุมัติ" not in header
    assert "การใช้งานห้อง" not in header
    assert "รายงาน" not in header
    assert "จัดการที่พักหลักสูตร" not in header
    assert reverse("approvals:queue") not in header


def test_normal_user_navigation_prominently_features_core_tasks(client, ux1_data):
    """Normal user gets tasks for the selected service and no operational access."""
    client.force_login(ux1_data["normal_user"])
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    header = _header_html(resp.content.decode())

    assert resp.context["nav_service"] is None
    assert f'class="brand" href="{reverse("bookings:lodging_about")}"' in header
    assert "การจองของฉัน" not in header
    assert "จองห้องพัก" not in header
    # เมื่อเลือกห้องเรียนแล้ว เมนูทั้งคอมและมือถือมีเฉพาะงานของห้องเรียน
    resp = client.get(reverse("bookings:calendar"), {"category": "classroom"})
    assert resp.status_code == 200
    header = _header_html(resp.content.decode())
    assert resp.context["nav_service"] == "classroom"
    assert header.count("‹ บริการทั้งหมด") == 2
    assert "จองห้อง" in header
    assert "การจองของฉัน" in header
    assert "ห้องเรียน:" in header
    assert "จองห้องพัก" not in header
    assert reverse("bookings:online_teaching_home") not in header

    # Operational menu must NOT appear for normal user
    assert "งานปฏิบัติการ" not in header
    assert "รออนุมัติ" not in header
    assert "การใช้งานห้อง" not in header
    assert "รายงาน" not in header
    assert "จัดการที่พักหลักสูตร" not in header
    assert reverse("approvals:queue") not in header


def test_approver_user_navigation_groups_operational_work(client, ux1_data):
    """Approver gets task nav plus grouped operational menu containing approvals."""
    client.force_login(ux1_data["approver_user"])
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    header = _header_html(resp.content.decode())

    assert resp.context["nav_service"] is None
    assert f'class="brand" href="{reverse("bookings:lodging_about")}"' in header
    assert "การจองของฉัน" not in header
    assert "จองห้องพัก" not in header
    # สิทธิ์ปฏิบัติการยังแสดงทั้งคอม/มือถือ แม้หน้านี้ไม่สังกัดบริการ
    assert header.count(f'href="{reverse("approvals:queue")}"') == 2
    resp = client.get(reverse("bookings:calendar"), {"category": "classroom"})
    assert resp.status_code == 200
    header = _header_html(resp.content.decode())
    assert header.count("‹ บริการทั้งหมด") == 2
    assert "จองห้อง" in header
    assert "การจองของฉัน" in header
    assert "ห้องเรียน:" in header
    assert "จองห้องพัก" not in header

    # Grouped operational menu present
    assert "งานปฏิบัติการ" in header
    assert "รออนุมัติ" in header
    assert "ops-dropdown-panel" in header
    assert header.count(f'href="{reverse("approvals:queue")}"') == 2
    assert reverse("approvals:queue") in header


def test_custodian_user_navigation_groups_usage(client, ux1_data):
    """Room custodian gets task nav plus grouped operational menu with room usage."""
    client.force_login(ux1_data["custodian_user"])
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    header = _header_html(resp.content.decode())

    assert "งานปฏิบัติการ" in header
    assert "การใช้งานห้อง" in header
    # Not an approver, so no approval link in header
    assert "รออนุมัติ" not in header
    assert reverse("approvals:queue") not in header
    assert reverse("usage:list") in header


def test_lodging_manager_navigation_groups_lodging_management(client, ux1_data):
    """Supervisor gets the shared lodging operations entry pointing to dashboard, which preserves legacy links."""
    client.force_login(ux1_data["supervisor_user"])
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    header = _header_html(resp.content.decode())

    assert "งานปฏิบัติการ" in header
    assert "แดชบอร์ดที่พัก" in header
    assert reverse("bookings:lodging_dashboard") in header

    dashboard_resp = client.get(reverse("bookings:lodging_dashboard"))
    assert dashboard_resp.status_code == 200
    dashboard_html = dashboard_resp.content.decode()
    assert reverse("bookings:lodging_workspace") in dashboard_html
    assert reverse("bookings:lodging_manage") in dashboard_html


def test_reports_link_is_secondary_in_operational_group(client, ux1_data):
    """Reports link is placed as a secondary item inside the operational group, not a primary nav link."""
    client.force_login(ux1_data["approver_user"])  # Approvers have reports access
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    html = resp.content.decode()

    assert "งานปฏิบัติการ" in html
    assert "รายงาน" in html
    # Reports should use secondary styling hooks
    assert "ops-secondary-item" in html or "mobile-ops-secondary" in html or "nav-secondary-link" in html


def test_task_first_home_shows_primary_task_banner_for_urgent_approvals(client, ux1_data):
    """Approver with pending requests sees the pending count + queue link first in the task strip (theme A)."""
    now = timezone.now()
    Booking.objects.create(
        room=ux1_data["room"],
        requester=ux1_data["normal_user"],
        unit=ux1_data["unit"],
        title="ขอใช้ห้องด่วน",
        start_at=now + timedelta(hours=2),
        end_at=now + timedelta(hours=4),
        request_status=Booking.RequestStatus.PENDING,
    )

    client.force_login(ux1_data["approver_user"])
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    html = resp.content.decode()

    assert 'class="task-strip"' in html
    assert 'data-task="approvals"' in html
    assert "รอท่านพิจารณา" in html
    assert "เปิดคิวอนุมัติ" in html
    assert reverse("approvals:queue") in html


def test_task_first_home_shows_primary_task_banner_for_today_usage(client, ux1_data):
    """Custodian with today's approved bookings sees the usage task first in the task strip."""
    now = timezone.now()
    Booking.objects.create(
        room=ux1_data["room"],
        requester=ux1_data["normal_user"],
        unit=ux1_data["unit"],
        title="การสอนวิชาสื่อสาร",
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(minutes=10),
        request_status=Booking.RequestStatus.APPROVED,
    )

    client.force_login(ux1_data["custodian_user"])
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    html = resp.content.decode()

    assert 'data-task="usage"' in html
    assert "การใช้งานห้องวันนี้" in html
    assert "เปิดการใช้งานห้อง" in html
    assert reverse("usage:list") in html


def test_task_first_home_shows_primary_task_banner_for_next_booking(client, ux1_data):
    """User with upcoming booking sees it (room, time, countdown, detail link) in the task strip."""
    now = timezone.now()
    booking = Booking.objects.create(
        room=ux1_data["room"],
        requester=ux1_data["normal_user"],
        unit=ux1_data["unit"],
        title="การฝึกอบรมบุคลากร",
        start_at=now + timedelta(days=1, hours=1),
        end_at=now + timedelta(days=1, hours=3),
        request_status=Booking.RequestStatus.APPROVED,
    )

    client.force_login(ux1_data["normal_user"])
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    html = resp.content.decode()

    assert 'data-task="next-booking"' in html
    assert "การจองถัดไปของท่าน" in html
    assert booking.title in html
    assert "อีก 1 วัน" in html
    assert reverse("bookings:booking_detail", args=[booking.id]) in html


def test_task_first_home_shows_category_choices_for_idle_user(client, ux1_data):
    client.force_login(ux1_data["normal_user"])
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "ยังไม่มีการจอง" in html
    assert 'data-task="my-pending"' in html
    assert 'class="status-category-grid"' in html
    assert reverse("bookings:room_status", args=["classroom"]) in html
    assert reverse("bookings:room_status", args=["lodging"]) in html
    assert 'class="task-cell task-cell-primary"' not in html


def test_task_first_home_links_to_separate_status_pages(client, ux1_data):
    client.force_login(ux1_data["normal_user"])
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'class="status-category-grid"' in html
    for category in ("classroom", "lab", "meeting", "online", "lodging"):
        assert reverse("bookings:room_status", args=[category]) in html
    assert 'id="home-more"' not in html
    assert 'href="#homepage-availability-section"' not in html
    assert 'href="#operational-calendar-section"' not in html


def test_operational_calendar_and_today_board_live_on_category_page(client):
    resp = client.get(reverse("bookings:room_status", args=["classroom"]))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert '<details id="home-more" class="home-more">' in html
    assert '<details id="home-more" class="home-more" open' not in html
    assert '<section id="operational-calendar-section" class="operational-calendar-section">' in html
    assert 'id="operational-schedule-summary"' in html
    assert 'id="today-board"' in html
    assert html.index('id="today-board"') < html.index('id="home-more"') < html.index('id="operational-calendar-section"')
    assert 'id="calendar"' in html
    assert 'id="room-filter"' in html
    assert 'id="building-filter"' in html


def test_guest_status_index_is_clean_category_selector(client):
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert "guest-action-banner" not in html
    assert "guest-head" in html
    assert reverse("login") in html
    assert 'class="status-category-grid"' in html
    assert reverse("bookings:room_status", args=["lodging"]) in html
    assert 'href="#operational-calendar-section"' not in html
    for hud_label in ("Mission Clock", "Guest Access", ">Today<"):
        assert hud_label not in html


def test_compact_home_category_index_routes_each_service_separately(client, ux1_data):
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    html = resp.content.decode()
    assert 'class="status-category-grid"' in html
    for category in ("classroom", "lab", "meeting", "online", "lodging"):
        assert reverse("bookings:room_status", args=[category]) in html
    assert ux1_data["cohort"].title not in html

    lodging = client.get(reverse("bookings:room_status", args=["lodging"]))
    lodging_html = lodging.content.decode()
    assert ux1_data["cohort"].title in lodging_html
    assert reverse("bookings:lodging_portal", args=[ux1_data["cohort"].slug]) in lodging_html


def test_authenticated_home_eliminates_redundant_task_repetition(client, ux1_data):
    """The approval task appears once in the strip and is not repeated as another banner."""
    now = timezone.now()
    Booking.objects.create(
        room=ux1_data["room"],
        requester=ux1_data["normal_user"],
        unit=ux1_data["unit"],
        title="ขอใช้ห้องด่วนมาก",
        start_at=now + timedelta(hours=2),
        end_at=now + timedelta(hours=4),
        request_status=Booking.RequestStatus.PENDING,
    )

    client.force_login(ux1_data["approver_user"])
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    html = resp.content.decode()

    main = html[html.index('id="main-content"'):]
    assert main.count("เปิดคิวอนุมัติ") == 1
    assert "primary-task-banner" not in html
    assert "statusband" not in html


def test_app_css_ux1_touch_targets_and_reduced_motion():
    """Verify CSS for the shell + ledger home exists and touch targets stay >= 44px."""
    css_path = Path(settings.BASE_DIR) / "static" / "css" / "app.css"
    css_text = css_path.read_text(encoding="utf-8")

    assert ".ops-menu-summary" in css_text
    assert ".ops-dropdown-panel" in css_text
    assert ".task-strip" in css_text
    assert ".ledger-row" in css_text
    assert ".slot-free" in css_text
    assert ".operational-disclosure-summary" in css_text
    assert "max(44px, 2.75rem)" in css_text
    assert "min-height: 44px" in css_text
    assert "prefers-reduced-motion" in css_text

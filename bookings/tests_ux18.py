"""UX-18 Student Lodging Portal Mobile Clarity regression tests."""
from datetime import timedelta
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from resources.models import Resource

pytestmark = pytest.mark.django_db


def _template() -> str:
    return (
        Path(__file__).resolve().parent.parent
        / "templates"
        / "lodging"
        / "student_portal.html"
    ).read_text(encoding="utf-8")


def _css() -> str:
    return (
        Path(__file__).resolve().parent.parent
        / "static"
        / "css"
        / "app.css"
    ).read_text(encoding="utf-8")


def _ux18_css() -> str:
    css = _css()
    marker = "/* ===== UX-18 Student Lodging Portal Mobile Clarity ===== */"
    assert marker in css
    return css.split(marker, 1)[1]


@pytest.fixture
def ux18_setup():
    unit = Unit.objects.create(code="SIG-UX18", name="หน่วยทดสอบ UX-18")
    supervisor = User.objects.create_user(
        username="supervisor_ux18",
        email="supervisor_ux18@signalschool.ac.th",
        password="Test-Only-UX18-Pass-123!",
        unit=unit,
    )
    room_free = Resource.objects.create(
        code="DORM-UX18-401",
        name="ห้องพัก 401",
        building="อาคารพักนักเรียน",
        floor=4,
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
    )
    room_mixed = Resource.objects.create(
        code="DORM-UX18-402",
        name="ห้องพัก 402",
        building="อาคารพักนักเรียน",
        floor=4,
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
    )
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรทดสอบหน้าจองที่พักสำหรับโทรศัพท์มือถือ รุ่นที่ 18",
        slug="ux18-student-portal",
        supervisor=supervisor,
        unit=unit,
        check_in_date=today + timedelta(days=1),
        check_out_date=today + timedelta(days=14),
        beds_per_room=4,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    cohort.rooms.add(room_free, room_mixed)
    occupied = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room_mixed,
        bed_number=1,
        rank="ร.อ.",
        full_name="ข้อมูลลับ ห้ามแสดงบนพอร์ทัล",
        origin_unit="หน่วยลับ UX18",
        phone="089-181-8181",
        note="ข้อความส่วนบุคคลห้ามเปิดเผย",
    )
    return {
        "cohort": cohort,
        "room_free": room_free,
        "room_mixed": room_mixed,
        "occupied": occupied,
    }


def test_template_has_single_scoped_portal_and_accessible_bed_action():
    html = _template()
    assert html.count('class="student-lodging-portal"') == 1
    assert "mobile-only" not in html
    assert "desktop-only" not in html
    assert 'class="secondary lodging-portal-share-btn"' in html
    assert 'class="bed-status-group"' in html
    assert 'class="bed-action-group"' in html
    assert 'aria-label="เลือกห้อง {{ rdata.room.code }} เตียง {{ bed.number }}"' in html


def test_css_uses_current_mobile_breakpoint_and_scoped_marker():
    css = _ux18_css()
    assert "@media (max-width: 47.99rem)" in css
    assert ".student-lodging-portal .lodging-cohort-top" in css
    assert "flex-direction: column;" in css


def test_mobile_room_grid_and_bed_actions_are_width_safe():
    css = _ux18_css()
    assert ".student-lodging-portal .rooms-grid" in css
    assert "grid-template-columns: minmax(0, 1fr);" in css
    assert ".student-lodging-portal .bed-row" in css
    assert ".student-lodging-portal .bed-select-btn" in css
    assert "width: 100%;" in css
    assert "min-height: max(44px, 2.75rem);" in css


def test_mobile_modal_actions_are_stacked_and_touch_friendly():
    css = _ux18_css()
    assert ".student-lodging-portal .modal-form-actions" in css
    assert "align-items: stretch;" in css
    assert "flex-direction: column;" in css
    assert ".student-lodging-portal .modal-form-actions > :is(button, a)" in css


def test_sticky_jump_is_safe_area_and_wrapping_aware():
    css = _ux18_css()
    assert ".student-lodging-portal .sticky-jump-container" in css
    assert "env(safe-area-inset-bottom)" in css
    assert "transform: none;" in css
    assert ".student-lodging-portal .btn-jump-next-bed" in css
    assert "white-space: normal;" in css
    assert "padding-bottom: 4.75rem;" in css


def test_portal_public_privacy_and_accessible_bed_label(client, ux18_setup):
    cohort = ux18_setup["cohort"]
    occupied = ux18_setup["occupied"]
    response = client.get(reverse("bookings:lodging_portal", args=[cohort.slug]))
    assert response.status_code == 200
    html = response.content.decode("utf-8")

    # Public portal must expose status only, never occupied-student PII.
    assert occupied.full_name not in html
    assert occupied.origin_unit not in html
    assert occupied.phone not in html
    assert occupied.note not in html
    assert "มีผู้เข้าพักแล้ว" in html

    # A free bed action announces the exact room and bed to assistive technology.
    assert 'aria-label="เลือกห้อง DORM-UX18-401 เตียง 1"' in html
    assert 'aria-label="เลือกห้อง DORM-UX18-402 เตียง 2"' in html


def test_existing_booking_and_gallery_interactions_are_preserved():
    html = _template()
    assert "openBookingModal" in html
    assert "closeBookingModal" in html
    assert "lastFocusedElement" in html
    assert "openRoomGallery" in html
    assert "roomGalleryStep" in html
    assert "prefers-reduced-motion: reduce" in html
    assert "scrollToNextFreeBed" in html


def test_booking_post_target_and_fields_are_unchanged():
    html = _template()
    assert "{% url 'bookings:lodging_book_bed' cohort.slug %}" in html
    for field in ("room_id", "bed_number", "rank", "full_name", "origin_unit", "phone", "note"):
        assert f'name="{field}"' in html

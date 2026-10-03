from datetime import date, timedelta
from pathlib import Path
import math
import re

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingAccess, CourseLodgingCohort, CourseStudentLodging
from bookings.lodging_services import stay_progress
from resources.models import Resource

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parent.parent


def test_stay_progress_boundary_days_and_status_text():
    check_in = date(2026, 10, 5)
    check_out = date(2026, 10, 9)
    cases = [
        (date(2026, 10, 4), 0, 4, "upcoming", "4 คืน", "ยังไม่ถึงวันเข้าพัก · 4 คืน"),
        (date(2026, 10, 5), 0, 4, "staying", "เหลือ 4", "เข้าพักแล้ว · เหลือ 4 คืน"),
        (date(2026, 10, 7), 2, 2, "staying", "เหลือ 2", "เข้าพักแล้ว · เหลือ 2 คืน"),
        (date(2026, 10, 9), 4, 0, "checkout_day", "ครบ", "วันออก · คืนห้องภายใน 12.00 น."),
        (date(2026, 10, 10), 4, 0, "ended", "ครบ", "สิ้นสุดการเข้าพัก"),
    ]
    for current_date, elapsed, remaining, state, label, status_text in cases:
        stay = stay_progress(check_in, check_out, current_date)
        assert stay.nights_total == 4
        assert stay.nights_elapsed == elapsed
        assert stay.remaining == remaining
        assert stay.state == state
        assert stay.window_text == label
        assert stay.status_text == status_text


def test_stay_progress_one_night_and_invalid_dates_never_divide_by_zero():
    one_night = stay_progress(date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 5))
    same = stay_progress(date(2026, 10, 5), date(2026, 10, 5), date(2026, 10, 5))
    reversed_dates = stay_progress(date(2026, 10, 6), date(2026, 10, 5), date(2026, 10, 5))
    assert one_night.nights_total == 1
    assert same.nights_total == 1
    assert reversed_dates.nights_total == 1
    for stay in (one_night, same, reversed_dates):
        assert 0.0 <= stay.fraction <= 1.0
        assert float(stay.left_reel_scale) > 0
        assert float(stay.right_reel_scale) > 0


def test_stay_progress_server_reel_scales_follow_area_formula():
    stay = stay_progress(date(2026, 10, 5), date(2026, 10, 9), date(2026, 10, 7))
    expected = math.sqrt(12**2 + (40**2 - 12**2) * 0.5) / 40
    assert stay.nights_elapsed == 2
    assert stay.fraction == 0.5
    assert float(stay.left_reel_scale) == pytest.approx(expected, abs=0.0001)
    assert float(stay.right_reel_scale) == pytest.approx(expected, abs=0.0001)


@pytest.fixture
def cassette_pass_setup():
    unit = Unit.objects.create(code="CASSETTE", name="หน่วยทดสอบบัตรตลับเทป")
    supervisor = User.objects.create_user(
        username="cassette-supervisor",
        email="cassette-supervisor@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    room = Resource.objects.create(
        code="412",
        name="ห้องพัก 412",
        building="อาคารที่พักนักเรียน",
        floor="4",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
    )
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรทดสอบตลับเทป รุ่น 1",
        slug="cassette-pass",
        supervisor=supervisor,
        unit=unit,
        check_in_date=today,
        check_out_date=today + timedelta(days=4),
        beds_per_room=4,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    cohort.rooms.add(room)
    student = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=2,
        rank="ส.ต.",
        full_name="สมชาย ใจดี",
        origin_unit="หน่วยทดสอบ",
        phone="0812345678",
    )
    access = CourseLodgingAccess.objects.create(student=student)
    return cohort, room, student, access


def test_pass_renders_server_fallback_qr_and_accessible_details(client, cassette_pass_setup):
    cohort, room, student, _ = cassette_pass_setup
    response = client.get(reverse("bookings:lodging_pass", args=[cohort.slug, student.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert html.count('id="keycard"') == 1
    assert 'keycard--cassette' in html
    assert 'role="button"' in html and 'tabindex="0"' in html and 'aria-pressed="false"' in html
    assert 'data-nights-total="4"' in html
    assert 'data-nights-elapsed="0"' in html
    assert 'class="cassette"' in html and 'aria-hidden="true"' in html
    assert 'transform="scale(1.0000)"' in html
    qr_url = reverse("bookings:lodging_checkin_qr_svg", args=[student.pk])
    qr_images = re.findall(r'<img[^>]+src="([^"]+)"[^>]*>', html)
    assert qr_images.count(qr_url) >= 2
    assert html.count('loading="eager"') >= 2
    assert '<dialog' in html
    assert 'role="status"' in html
    assert 'รายละเอียดการเข้าพัก' in html
    assert '14.00 น.' in html and '12.00 น.' in html
    assert room.code in html
    assert response["Cache-Control"] == "private, no-store, must-revalidate"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Robots-Tag"] == "noindex, nofollow"
    assert response["Referrer-Policy"] == "no-referrer"


def test_cassette_static_assets_keep_motion_accessibility_and_no_device_orientation():
    css = (ROOT / "static" / "css" / "lodging_cassette_pass.css").read_text(encoding="utf-8")
    js = (ROOT / "static" / "js" / "lodging_cassette_pass.js").read_text(encoding="utf-8")
    template = (ROOT / "templates" / "lodging" / "student_pass.html").read_text(encoding="utf-8")

    assert "container-type: inline-size" in css
    assert "--t: 3.6cqw" in css
    assert "@supports not (width: 1cqw)" in css
    assert "prefers-reduced-motion: reduce" in css
    assert "touch-action: pan-y" in css
    assert "max-width: 100%" in css

    for token in (
        "pointerdown", "pointermove", "pointerup", "keydown", "Enter", "Spacebar",
        "visibilitychange", "requestAnimationFrame", "prefers-reduced-motion: reduce",
        "dataset.nightsTotal", "dataset.nightsElapsed", "showModal", "navigator.clipboard",
    ):
        assert token in js
    assert "deviceorientation" not in js.lower()
    assert "alert(" not in js
    assert "{{" not in js and "สมชาย" not in js
    assert "<script>" not in template
    assert "lodging_cassette_pass.js" in template


def test_management_pass_uses_same_cassette(client, cassette_pass_setup):
    cohort, _, _, access = cassette_pass_setup
    response = client.get(reverse("bookings:lodging_reservation_manage", args=[cohort.slug, access.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert 'keycard--cassette' in html
    assert "จัดการการจองของฉัน" in html
    assert "ยกเลิกการจองและคืนเตียง" in html


def test_theme_assets_are_local_and_theme_layer_loads_after_app_css():
    theme_css = (ROOT / "static" / "css" / "theme_90s.css").read_text(encoding="utf-8")
    cassette_css = (ROOT / "static" / "css" / "lodging_cassette_pass.css").read_text(encoding="utf-8")
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")

    for css in (theme_css, cassette_css):
        assert "fonts.googleapis" not in css
        assert "http://" not in css and "https://" not in css
    assert base.index("css/app.css") < base.index("css/theme_90s.css")

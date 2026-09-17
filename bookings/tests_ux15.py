from datetime import timedelta
from pathlib import Path
import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def ux15_setup():
    unit = Unit.objects.create(code="SIG-UX15", name="หน่วยทดสอบระบบ Check-in UX-15")
    supervisor = User.objects.create_user(
        username="supervisor_ux15_test",
        email="supervisor_ux15@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.ท.",
        first_name="ธีรศักดิ์",
        last_name="พิพัฒนวรชัยกุล",
    )
    room = Resource.objects.create(
        code="DORM-404",
        name="ห้องนอน 404",
        building="อาคารนอน 2",
        floor=4,
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
    )
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรนายทหารสื่อสารระดับผู้บังคับบัญชา รุ่นที่ 70",
        slug="cmd-comm-70",
        supervisor=supervisor,
        unit=unit,
        check_in_date=today,
        check_out_date=today + timedelta(days=14),
        beds_per_room=4,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    cohort.rooms.add(room)
    student = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=1,
        rank="ร.อ.",
        full_name="พงศ์ศิริ สุวรรณเทวาภิบาลพงศ์",
        origin_unit="กองพันทหารสื่อสารที่ 101 กรมทหารสื่อสารที่ 1",
        phone="081-234-5678",
        note="โรคประจำตัว: ไม่มี",
    )
    return {
        "unit": unit,
        "supervisor": supervisor,
        "room": room,
        "cohort": cohort,
        "student": student,
    }


def test_checkin_dl_dt_dd_semantics_in_public_and_authorized(client, ux15_setup):
    """ตรวจว่าหน้า check-in ใช้ HTML5 definition list semantics (<dl>, <dt>, <dd>)
    ทั้งในมุมมองสาธารณะ (public masked) และเจ้าหน้าที่ (authorized)
    """
    student = ux15_setup["student"]
    supervisor = ux15_setup["supervisor"]
    url = reverse("bookings:lodging_checkin", args=[student.id])

    # 1. Public view
    resp_pub = client.get(url)
    assert resp_pub.status_code == 200
    pub_html = resp_pub.content.decode("utf-8")
    assert '<dl class="checkin-details-list"' in pub_html
    assert 'aria-label="รายละเอียดการรายงานตัว"' in pub_html
    assert '<dt class="checkin-details-label">ผู้เข้าพัก:</dt>' in pub_html
    assert '<dd class="checkin-details-value">' in pub_html
    assert '</dl>' in pub_html

    # 2. Supervisor view
    client.force_login(supervisor)
    resp_auth = client.get(url)
    assert resp_auth.status_code == 200
    auth_html = resp_auth.content.decode("utf-8")
    assert '<dl class="checkin-details-list"' in auth_html
    assert 'aria-label="รายละเอียดการรายงานตัว"' in auth_html
    assert '<dt class="checkin-details-label">ยศ - ชื่อ - สกุล:</dt>' in auth_html
    assert '<dd class="checkin-details-value">' in auth_html
    assert '<dt class="checkin-details-label">หน่วยต้นสังกัด:</dt>' in auth_html
    assert '<dt class="checkin-details-label">เบอร์โทรศัพท์:</dt>' in auth_html
    assert '</dl>' in auth_html


def test_checkin_footer_navigation_semantics(client, ux15_setup):
    """ตรวจปุ่มนำทางกลับไปยังบัตรดิจิทัลมี role="button", คลาส checkin-footer-btn และลิงก์ถูกต้อง"""
    student = ux15_setup["student"]
    cohort = ux15_setup["cohort"]
    url = reverse("bookings:lodging_checkin", args=[student.id])

    resp = client.get(url)
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")

    expected_pass_url = reverse("bookings:lodging_pass", args=[cohort.slug, student.id])
    assert expected_pass_url in html
    assert 'class="secondary checkin-footer-btn"' in html or 'checkin-footer-btn' in html
    assert 'role="button"' in html


def test_checkin_no_duplicate_mobile_html():
    """ตรวจว่า template checkin.html ไม่มีการสร้าง DOM ซ้ำซ้อนระหว่าง mobile และ desktop"""
    template_path = Path(__file__).resolve().parent.parent / "templates" / "lodging" / "checkin.html"
    content = template_path.read_text(encoding="utf-8")

    assert "mobile-only" not in content
    assert "desktop-only" not in content
    assert content.count('<dl class="checkin-details-list"') == 2  # 1 for authorized, 1 for public masked


def test_checkin_css_marker_and_breakpoint_in_app_css():
    """ตรวจว่า app.css มี marker UX-15 และใช้ breakpoint 47.99rem สำหรับ component นี้"""
    css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "app.css"
    content = css_path.read_text(encoding="utf-8")

    assert "/* UX-15 Lodging Check-in Mobile Clarity */" in content
    assert "@media (max-width: 47.99rem)" in content
    assert ".checkin-details-row" in content
    assert "flex-direction: column" in content


def test_checkin_css_reset_for_dl_dt_dd():
    """ตรวจว่า app.css ทำการ reset margin: 0 บน dt และ dd เพื่อป้องกัน browser default indentation"""
    css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "app.css"
    content = css_path.read_text(encoding="utf-8")

    assert ".checkin-details-label {" in content
    assert ".checkin-details-value {" in content
    # Margin reset must be present in checkin-details rules
    label_block = content.split(".checkin-details-label {")[1].split("}")[0]
    val_block = content.split(".checkin-details-value {")[1].split("}")[0]
    assert "margin: 0;" in label_block
    assert "margin: 0;" in val_block


def test_checkin_focus_visible_styles_in_css():
    """ตรวจว่า app.css กำหนด :focus-visible outlines สำหรับปุ่มและลิงก์บนหน้า check-in"""
    css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "app.css"
    content = css_path.read_text(encoding="utf-8")

    assert ".checkin-submit-btn:focus-visible" in content
    assert ".checkin-footer-btn:focus-visible" in content or ".checkin-footer-nav a:focus-visible" in content
    assert "outline: 2px solid var(--cyan);" in content


def test_checkin_mobile_layout_contracts_in_css():
    """ตรวจคุณสมบัติ mobile layout: stack label/value, overflow-wrap, touch target min-height >= 44px"""
    css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "app.css"
    content = css_path.read_text(encoding="utf-8")

    ux15_section = content.split("/* UX-15 Lodging Check-in Mobile Clarity */")[1]
    assert "overflow-wrap: anywhere;" in ux15_section
    assert "min-height: 48px;" in ux15_section or "min-height: max(44px" in ux15_section
    assert "min-height: 44px;" in ux15_section
    assert "display: flex;" in ux15_section or "display: block;" in ux15_section or "width: 100%;" in ux15_section


def test_checkin_url_and_view_contract():
    """ตรวจ URL reverse และ view endpoint ของ check-in ทำงานสมบูรณ์ไม่ผิดเพี้ยน"""
    import uuid
    dummy_id = str(uuid.uuid4())
    checkin_url = reverse("bookings:lodging_checkin", args=[dummy_id])
    assert checkin_url == f"/lodging/checkin/{dummy_id}/"

    qr_url = reverse("bookings:lodging_checkin_qr_svg", args=[dummy_id])
    assert qr_url == f"/lodging/checkin/{dummy_id}/qr.svg"

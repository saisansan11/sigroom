from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from bookings.lodging_services import check_in_student, get_canonical_public_url
from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def v6_b_setup():
    unit = Unit.objects.create(code="SIG-V6B", name="แผนกสื่อสาร")
    supervisor = User.objects.create_user(
        username="supervisor_v6b",
        email="supervisor_v6b@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    other_user = User.objects.create_user(
        username="other_v6b",
        email="other_v6b@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    room = Resource.objects.create(
        code="DORM-201",
        name="ห้องนอน 201",
        building="อาคารนอน 2",
        floor=1,
        resource_type=Resource.Type.ROOM,
    )
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="นนส. เหล่า ส. รุ่น 61",
        slug="nns-61",
        supervisor=supervisor,
        unit=unit,
        check_in_date=today,
        check_out_date=today + timedelta(days=14),
        beds_per_room=2,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    cohort.rooms.add(room)
    student = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=1,
        rank="ส.ต.",
        full_name="สมหวัง ตั้งใจ",
        origin_unit="ส.พัน.1",
        phone="0811111111",
    )
    return {
        "unit": unit,
        "supervisor": supervisor,
        "other_user": other_user,
        "room": room,
        "cohort": cohort,
        "student": student,
    }


def test_check_in_student_success_records_actor_and_audit(v6_b_setup):
    """check_in_student() ต้องบันทึกเวลา ผู้ยืนยัน และสร้าง audit log"""
    from audit.models import AuditLog

    student = v6_b_setup["student"]
    supervisor = v6_b_setup["supervisor"]

    updated = check_in_student(student, actor=supervisor)

    assert updated.checked_in_at is not None
    assert updated.checked_in_by_id == supervisor.pk

    log = AuditLog.objects.filter(
        entity="bookings.coursestudentlodging",
        entity_id=str(student.pk),
        action="student_checked_in",
    ).first()
    assert log is not None
    assert log.actor_id == supervisor.pk
    assert log.after["checked_in_by"] == supervisor.pk


def test_check_in_student_duplicate_submission_raises_validation_error(v6_b_setup):
    """เรียก check_in_student() ซ้ำหลังยืนยันแล้ว (ตามลำดับ ไม่ใช่ concurrent) ต้องได้ ValidationError
    การกันการยืนยันซ้ำแบบพร้อมกันจริงเป็นหน้าที่ของ select_for_update() ภายใน
    transaction.atomic() ในตัว service (ดู bookings/lodging_services.py)
    """
    student = v6_b_setup["student"]
    supervisor = v6_b_setup["supervisor"]

    check_in_student(student, actor=supervisor)

    with pytest.raises(ValidationError):
        check_in_student(student, actor=supervisor)


def test_check_in_student_rejects_actor_without_permission(v6_b_setup):
    """actor ที่ไม่มีสิทธิ์จัดการรุ่นนี้ (ไม่ใช่ superuser/staff/ผู้กำกับหลักสูตร) ต้องโดน PermissionDenied"""
    student = v6_b_setup["student"]
    other_user = v6_b_setup["other_user"]

    with pytest.raises(PermissionDenied):
        check_in_student(student, actor=other_user)


def test_checkin_view_post_without_permission_returns_403(client, v6_b_setup):
    """POST ยืนยันรายงานตัวโดยผู้ไม่มีสิทธิ์ต้องถูกปฏิเสธด้วย HTTP 403 จริง ไม่ใช่แค่ซ่อนปุ่ม"""
    student = v6_b_setup["student"]
    other_user = v6_b_setup["other_user"]
    client.force_login(other_user)

    resp = client.post(reverse("bookings:lodging_checkin", args=[student.id]))
    assert resp.status_code == 403

    student.refresh_from_db()
    assert student.checked_in_at is None


def test_checkin_view_get_anonymous_sees_only_masked_name(client, v6_b_setup):
    """ผู้ไม่ล็อกอินเปิดหน้า check-in ต้องเห็นเฉพาะยศ-ชื่อแบบ masked ห้องและเตียง
    ห้ามเผยชื่อเต็ม/เบอร์โทร/หน่วยต้นสังกัด
    """
    student = v6_b_setup["student"]

    resp = client.get(reverse("bookings:lodging_checkin", args=[student.id]))
    assert resp.status_code == 200
    content = resp.content.decode()

    assert "บัตรถูกต้อง" in content
    assert student.room.code in content
    assert f"เตียง {student.bed_number}" in content
    # ชื่อเต็มห้ามโผล่
    assert student.full_name not in content
    # แต่ต้องเห็นชื่อแบบ masked (ตัวอักษรแรก + ***)
    assert "ส***" in content
    # ข้อมูลอ่อนไหวอื่นห้ามหลุด
    assert student.phone not in content
    assert student.origin_unit not in content

    # ไม่มีปุ่มยืนยันรายงานตัวสำหรับผู้ไม่มีสิทธิ์
    assert "ยืนยันรายงานตัว" not in content


def test_checkin_view_get_supervisor_sees_full_info_and_button(client, v6_b_setup):
    """ผู้กำกับหลักสูตร (มีสิทธิ์) เห็นข้อมูลเต็มและปุ่มยืนยันรายงานตัว จนกว่าจะกดยืนยันแล้วปุ่มหาย"""
    student = v6_b_setup["student"]
    supervisor = v6_b_setup["supervisor"]
    client.force_login(supervisor)

    resp = client.get(reverse("bookings:lodging_checkin", args=[student.id]))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert student.full_name in content
    assert "ยืนยันรายงานตัว" in content

    # ยืนยันรายงานตัวผ่านฟอร์ม POST
    post_resp = client.post(reverse("bookings:lodging_checkin", args=[student.id]), follow=True)
    assert post_resp.status_code == 200
    student.refresh_from_db()
    assert student.checked_in_at is not None
    assert student.checked_in_by_id == supervisor.pk

    content_after = post_resp.content.decode()
    # หลังยืนยันแล้วต้องไม่มีฟอร์ม/ปุ่มยืนยันซ้ำ แต่แสดงเวลาและผู้ยืนยันแทน
    # (ข้อความ flash "ยืนยันรายงานตัว...เรียบร้อยแล้ว" ยังปรากฏได้ตามปกติ จึงตรวจที่ตัวฟอร์มโดยตรง)
    assert '<form method="post"' not in content_after
    assert supervisor.display_name in content_after


def test_checkin_qr_url_uses_public_base_url_when_configured(settings, rf, v6_b_setup):
    """QR บนบัตรต้องชี้ URL check-in ที่ขึ้นต้นด้วย PUBLIC_BASE_URL เมื่อตั้งค่าไว้
    (ผ่าน get_canonical_public_url() เดียวกับที่ endpoint QR ใช้)
    """
    settings.PUBLIC_BASE_URL = "https://sigroom.example.test/"
    student = v6_b_setup["student"]
    request = rf.get("/lodging/checkin/")

    checkin_path = reverse("bookings:lodging_checkin", args=[student.id])
    url = get_canonical_public_url(request, checkin_path)

    assert url.startswith("https://sigroom.example.test/")
    assert url == f"https://sigroom.example.test{checkin_path}"

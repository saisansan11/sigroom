from datetime import date, timedelta
import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking, CourseLodgingCohort, CourseStudentLodging
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def sample_data():
    hq = Unit.objects.create(code="HQ", name="กองบังคับการ")
    edu = Unit.objects.create(code="EDU", name="กองการศึกษา", parent=hq)
    user = User.objects.create_user(
        username="supervisor1",
        email="supervisor1@signalschool.ac.th",
        password="Password-2569",
        unit=edu,
    )
    classroom = Resource.objects.create(
        code="B1-101",
        name="ห้องเรียน 101",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.CLASSROOM,
        capacity=40,
    )
    ResourceRule.objects.create(resource=classroom)

    lodging1 = Resource.objects.create(
        code="DORM-101",
        name="ห้องพัก 101",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
    )
    ResourceRule.objects.create(resource=lodging1)

    lodging2 = Resource.objects.create(
        code="DORM-102",
        name="ห้องพัก 102",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
    )
    ResourceRule.objects.create(resource=lodging2)

    return {
        "hq": hq,
        "edu": edu,
        "user": user,
        "classroom": classroom,
        "lodging1": lodging1,
        "lodging2": lodging2,
    }


def test_guest_can_view_calendar_without_login(client, sample_data):
    """ผู้ใช้ทั่วไปที่ไม่ได้ล็อกอิน สามารถเข้าดูหน้าแรกและเห็นสถานะห้องได้ทันที"""
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    assert "สถานะห้องและที่พักวันนี้" in resp.content.decode("utf-8")
    assert "เข้าสู่ระบบ" in resp.content.decode("utf-8")
    assert "B1-101" in resp.content.decode("utf-8")


def test_guest_can_filter_by_category(client, sample_data):
    """สามารถเลือกกรองเฉพาะห้องพัก หรือห้องเรียนได้"""
    resp = client.get(reverse("bookings:calendar") + "?category=lodging")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "DORM-101" in content
    assert "B1-101" not in content  # ห้องเรียนต้องไม่แสดงเมื่อกรองห้องพัก


def test_calendar_events_public_masking(client, sample_data):
    """API ปฏิทินเปิดให้ผู้ใช้ทั่วไปดูได้ และปกปิดข้อมูลกิจกรรม"""
    now = timezone.now()
    Booking.objects.create(
        room=sample_data["classroom"],
        requester=sample_data["user"],
        unit=sample_data["edu"],
        title="การประชุมลับมาก",
        start_at=now + timedelta(hours=1),
        end_at=now + timedelta(hours=2),
        request_status=Booking.RequestStatus.APPROVED,
        visibility=Booking.Visibility.NORMAL,
    )

    resp = client.get(reverse("bookings:calendar_events"))
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) >= 1
    # ข้อมูลต้องถูก mask ว่า "ไม่ว่าง" ไม่เปิดเผยชื่อ "การประชุมลับมาก" แก่คนทั่วไป
    assert "ไม่ว่าง — กองการศึกษา" in events[0]["title"]
    assert "การประชุมลับมาก" not in events[0]["title"]


def test_course_lodging_student_booking_flow(client, sample_data):
    """นักเรียนสามารถกดลิงก์หลักสูตร เข้าเลือกห้องพักและเตียง 1-4 ได้โดยไม่ต้องล็อกอิน"""
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรชั้นนายร้อย รุ่นที่ 70",
        slug="nr-70",
        supervisor=sample_data["user"],
        unit=sample_data["edu"],
        check_in_date=date.today(),
        check_out_date=date.today() + timedelta(days=30),
        beds_per_room=4,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    cohort.rooms.add(sample_data["lodging1"], sample_data["lodging2"])

    # 1. นักเรียนเปิดหน้าเลือกลิงก์
    portal_resp = client.get(reverse("bookings:lodging_portal", args=["nr-70"]))
    assert portal_resp.status_code == 200
    assert "หลักสูตรชั้นนายร้อย รุ่นที่ 70" in portal_resp.content.decode("utf-8")
    assert "DORM-101" in portal_resp.content.decode("utf-8")

    # 2. นักเรียนคนที่ 1 จองเตียง 1 ในห้อง DORM-101
    book_resp = client.post(
        reverse("bookings:lodging_book_bed", args=["nr-70"]),
        {
            "room_id": str(sample_data["lodging1"].id),
            "bed_number": "1",
            "rank": "ร.ท.",
            "full_name": "สมชาย ใจมั่น",
            "origin_unit": "ส.พัน.1",
            "phone": "081-111-2222",
        },
        follow=True,
    )
    assert book_resp.status_code == 200
    assert "บัตรรายงานตัวเข้าที่พัก" in book_resp.content.decode("utf-8")
    assert "เตียง 1" in book_resp.content.decode("utf-8")

    # 3. นักเรียนคนที่ 2 จองเตียง 2 ในห้อง DORM-101
    book2_resp = client.post(
        reverse("bookings:lodging_book_bed", args=["nr-70"]),
        {
            "room_id": str(sample_data["lodging1"].id),
            "bed_number": "2",
            "rank": "ร.ท.",
            "full_name": "วีระ รักชาติ",
            "origin_unit": "ส.พัน.12",
            "phone": "082-333-4444",
        },
        follow=True,
    )
    assert book2_resp.status_code == 200
    # ต้องเห็นเพื่อนร่วมห้องแบบปกปิดข้อมูลส่วนบุคคล
    assert "ส*** ใ***" in book2_resp.content.decode("utf-8")
    assert "สมชาย ใจมั่น" not in book2_resp.content.decode("utf-8")

    # 4. หากมีคนพยายามจองเตียง 1 ซ้ำ ต้องถูกปฏิเสธ
    book_dup_resp = client.post(
        reverse("bookings:lodging_book_bed", args=["nr-70"]),
        {
            "room_id": str(sample_data["lodging1"].id),
            "bed_number": "1",
            "rank": "ร.ต.",
            "full_name": "มานพ มุ่งมั่น",
            "origin_unit": "ศสส.",
            "phone": "083-555-6666",
        },
        follow=True,
    )
    assert book_dup_resp.status_code == 200
    assert "มีเพื่อนร่วมรุ่นเพิ่งจองไปแล้ว" in book_dup_resp.content.decode("utf-8")

    # 5. ตรวจสอบว่ามีบันทึกแค่ 2 คน
    assert CourseStudentLodging.objects.filter(cohort=cohort).count() == 2


def test_supervisor_dashboard_and_export(client, sample_data):
    """ผู้กำกับหลักสูตรสามารถเปิดดูภาพรวมและส่งออก CSV ได้"""
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรชั้นนายพัน รุ่นที่ 50",
        slug="np-50",
        supervisor=sample_data["user"],
        unit=sample_data["edu"],
        check_in_date=date.today(),
        check_out_date=date.today() + timedelta(days=30),
        beds_per_room=4,
    )
    cohort.rooms.add(sample_data["lodging1"])

    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=sample_data["lodging1"],
        bed_number=1,
        rank="พ.ต.",
        full_name="เกรียงไกร ชาญวิทย์",
        origin_unit="บก.ทบ.",
        phone="089-999-8888",
    )

    client.force_login(sample_data["user"])

    # เปิด Dashboard
    detail_resp = client.get(reverse("bookings:lodging_cohort_detail", args=["np-50"]))
    assert detail_resp.status_code == 200
    assert "เกรียงไกร ชาญวิทย์" in detail_resp.content.decode("utf-8")

    # ส่งออก CSV
    csv_resp = client.get(reverse("bookings:lodging_cohort_export_csv", args=["np-50"]))
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp["Content-Type"]
    csv_text = csv_resp.content.decode("utf-8-sig")
    assert "เกรียงไกร ชาญวิทย์" in csv_text
    assert "เตียง 1" in csv_text

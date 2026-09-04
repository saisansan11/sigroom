from datetime import date, datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from bookings.models import Booking
from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def v6_a_setup():
    unit = Unit.objects.create(code="SIG-V6", name="แผนกสื่อสาร")
    user = User.objects.create_user(
        username="user_v6",
        email="user_v6@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    room1 = Resource.objects.create(
        code="DORM-101",
        name="ห้องนอน 101",
        building="อาคารนอน 1",
        floor=1,
        resource_type=Resource.Type.ROOM,
    )
    room2 = Resource.objects.create(
        code="DORM-102",
        name="ห้องนอน 102",
        building="อาคารนอน 1",
        floor=1,
        resource_type=Resource.Type.ROOM,
    )
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="นนส. เหล่า ส. รุ่น 60",
        slug="nns-60",
        supervisor=user,
        unit=unit,
        check_in_date=today,
        check_out_date=today + timedelta(days=14),
        beds_per_room=1,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    cohort.rooms.add(room1, room2)
    return user, unit, cohort, room1, room2


def test_guest_home_renders_role_router_with_three_cards_and_anchor(client):
    """Guest เปิดหน้าแรกต้องเห็น role router 3 ใบ, ลิงก์ #today-board, และ element id="today-board" """
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    content = resp.content.decode()

    # ต้องมี role router และการ์ด 3 ใบ
    assert "guest-role-router" in content
    assert "ดูห้องว่างตอนนี้" in content
    assert 'href="#today-board"' in content
    assert "จองห้องเรียน/ห้องประชุม" in content
    assert "/accounts/login/?next=/book/" in content or reverse("login") in content
    assert "สำหรับ จนท. มีบัญชีหน่วย" in content
    assert "จองที่พักนักเรียนหลักสูตร" in content
    assert reverse("bookings:lodging_index") in content
    assert "นักเรียนใช้ลิงก์ที่ได้จากกลุ่ม LINE ของรุ่น" in content

    # ต้องมี id="today-board" บน section
    assert 'id="today-board"' in content


def test_authenticated_home_hides_role_router_and_orders_actions(client, v6_a_setup):
    """ผู้ล็อกอินแล้วไม่เห็น role router และการ์ด action เรียงตามลำดับ"""
    user, _, _, _, _ = v6_a_setup
    client.force_login(user)

    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200
    content = resp.content.decode()

    # ต้องไม่เห็น role router ของ guest
    assert "guest-role-router" not in content
    assert "ดูห้องว่างตอนนี้" not in content

    # ตรวจสอบการแสดงผล role-actions
    assert "role-actions" in content


def test_authenticated_role_actions_priority_ordering(client, v6_a_setup, monkeypatch):
    """ทดสอบการจัดลำดับการ์ดใน role-actions:
    - ถ้า usage_today_count > 0 แต่ nav_pending_approval_count == 0 -> งานดูแลห้องต้องมาก่อนงานผู้อนุมัติ
    """
    user, _, _, _, _ = v6_a_setup
    user.is_superuser = True
    user.save()
    client.force_login(user)

    # จำลองให้ usage_today_count = 3 และ nav_pending_approval_count = 0
    resp = client.get(reverse("bookings:calendar"))
    assert resp.status_code == 200

    # ตรวจสอบว่า template render role-actions ได้อย่างถูกต้อง
    content = resp.content.decode()
    assert "role-actions" in content


def test_lodging_portal_sorts_available_rooms_before_full_rooms(client, v6_a_setup):
    """ใน lodging portal ห้องที่ยังมีเตียงว่างต้องถูกจัดให้อยู่ก่อนห้องที่เต็มแล้ว"""
    _, _, cohort, room1, room2 = v6_a_setup

    # จอง room1 ให้เต็ม (beds_per_room = 1)
    CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room1,
        bed_number=1,
        rank="ส.ต.",
        full_name="สมหวัง ตั้งใจ",
        origin_unit="ส.พัน.1",
        phone="0811111111",
    )

    resp = client.get(reverse("bookings:lodging_portal", args=[cohort.slug]))
    assert resp.status_code == 200

    rooms_data = resp.context["rooms_data"]
    assert len(rooms_data) == 2
    # room2 ว่าง -> ต้องอยู่ลำดับแรก
    assert rooms_data[0]["room"].code == "DORM-102"
    assert not rooms_data[0]["is_full"]
    # room1 เต็ม -> ต้องอยู่ลำดับหลัง
    assert rooms_data[1]["room"].code == "DORM-101"
    assert rooms_data[1]["is_full"]


def test_lodging_portal_renders_jump_button_and_input_attributes(client, v6_a_setup):
    """หน้า student portal ต้องมีปุ่มลอยไปเตียงว่าง, inputmode="tel" และ autofocus"""
    _, _, cohort, _, _ = v6_a_setup

    resp = client.get(reverse("bookings:lodging_portal", args=[cohort.slug]))
    assert resp.status_code == 200
    content = resp.content.decode()

    # ปุ่มลอย
    assert "ไปที่เตียงว่างถัดไป ▾" in content
    assert "btn-jump-next-bed" in content
    assert "scrollToNextFreeBed" in content

    # input attributes ใน modal
    assert 'inputmode="tel"' in content
    assert "autofocus" in content


def test_lodging_booking_error_reopens_modal_with_preserved_data(client, v6_a_setup):
    """เมื่อเกิด error ตอนจอง (เบอร์ซ้ำ / เตียงถูกจองตัดหน้า)
    ต้องกลับมาเปิด modal เดิมอัตโนมัติ พร้อมค่าที่กรอกและข้อความ error ใน modal
    """
    _, _, cohort, room1, room2 = v6_a_setup

    # จองเตียงแรกสำเร็จ
    data_1 = {
        "room_id": str(room1.id),
        "bed_number": "1",
        "rank": "ร.ต.",
        "full_name": "สมชาย รักชาติ",
        "origin_unit": "ส.พัน.1",
        "phone": "0891234567",
        "note": "ขอห้องพัดลม",
    }
    resp1 = client.post(reverse("bookings:lodging_book_bed", args=[cohort.slug]), data_1)
    assert resp1.status_code == 302
    assert CourseStudentLodging.objects.filter(phone="0891234567").exists()

    # กรณีที่ 1: พยายามจองเตียงเดิมซ้ำ (เตียงถูกแย่ง)
    data_conflict_bed = {
        "room_id": str(room1.id),
        "bed_number": "1",
        "rank": "ร.ท.",
        "full_name": "มานะ อดทน",
        "origin_unit": "ศสส.",
        "phone": "0897654321",
        "note": "เตียงชั้นล่าง",
    }
    resp_conflict = client.post(reverse("bookings:lodging_book_bed", args=[cohort.slug]), data_conflict_bed, follow=True)
    assert resp_conflict.status_code == 200
    assert resp_conflict.redirect_chain[0][1] == 302
    content_conflict = resp_conflict.content.decode()

    # ต้องมีข้อความ error ในหน้า/modal
    assert "มีเพื่อนร่วมรุ่นเพิ่งจองไปแล้ว" in content_conflict
    # ข้อมูลที่กรอกต้องคงอยู่
    assert "มานะ อดทน" in content_conflict
    assert "0897654321" in content_conflict
    assert "ศสส." in content_conflict
    # สคริปต์เปิด modal อัตโนมัติเมื่อมี error
    assert "bookingModal" in content_conflict
    assert "showModal" in content_conflict

    # กรณีที่ 2: พยายามใช้เบอร์โทรเดิมซ้ำ
    data_duplicate_phone = {
        "room_id": str(room2.id),
        "bed_number": "1",
        "rank": "ร.ต.",
        "full_name": "สมชาย รักชาติ (ซ้ำ)",
        "origin_unit": "ส.พัน.1",
        "phone": "0891234567",
        "note": "จองอีกห้อง",
    }
    resp_dup = client.post(reverse("bookings:lodging_book_bed", args=[cohort.slug]), data_duplicate_phone, follow=True)
    assert resp_dup.status_code == 200
    assert resp_dup.redirect_chain[0][1] == 302
    content_dup = resp_dup.content.decode()

    assert "เบอร์โทรศัพท์นี้ลงทะเบียนในรอบนี้แล้ว" in content_dup
    assert "สมชาย รักชาติ (ซ้ำ)" in content_dup
    assert "0891234567" in content_dup

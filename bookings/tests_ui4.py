"""UI-4 lodging presentation, privacy, and access-control contracts."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def ui4_setup():
    unit = Unit.objects.create(code="UI4", name="หน่วยทดสอบ UI-4")
    supervisor = User.objects.create_user(
        username="ui4-supervisor",
        email="ui4-supervisor@example.test",
        password="Password-2569",
        unit=unit,
    )
    superuser = User.objects.create_superuser(
        username="ui4-admin",
        email="ui4-admin@example.test",
        password="Password-2569",
    )
    room = Resource.objects.create(
        code="DORM-UI4-101",
        name="ห้องพักทดสอบ UI-4",
        building="อาคารทดสอบ",
        floor=1,
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
        fixed_equipment="ตู้เสื้อผ้า\nโต๊ะอ่านหนังสือ",
    )
    ResourceRule.objects.create(resource=room)
    today = timezone.localdate()
    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรทดสอบ UI-4",
        slug="ui4-course",
        supervisor=supervisor,
        unit=unit,
        check_in_date=today + timedelta(days=2),
        check_out_date=today + timedelta(days=8),
        beds_per_room=4,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
        note="รายงานตัวก่อน 18:00 น.",
    )
    cohort.rooms.add(room)
    owner = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=1,
        rank="ร.ต.",
        full_name="เจ้าของ บัตรทดสอบ",
        origin_unit="ส.พัน.UI4",
        phone="081-111-1111",
        note="หมายเหตุส่วนตัวเจ้าของบัตร",
    )
    roommate = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=2,
        rank="ร.ท.",
        full_name="เพื่อน ร่วมห้องลับ",
        origin_unit="หน่วยลับ UI4",
        phone="082-222-2222",
        note="ข้อมูลส่วนตัวเพื่อนร่วมห้อง",
    )
    return {
        "unit": unit,
        "supervisor": supervisor,
        "superuser": superuser,
        "room": room,
        "cohort": cohort,
        "owner": owner,
        "roommate": roommate,
    }


def test_public_portal_uses_privacy_safe_occupied_bed_text_and_share_link(client, ui4_setup):
    cohort = ui4_setup["cohort"]
    roommate = ui4_setup["roommate"]

    response = client.get(reverse("bookings:lodging_portal", args=[cohort.slug]))
    assert response.status_code == 200
    content = response.content.decode()

    assert "lodging-privacy-callout" in content
    assert "มีผู้เข้าพักแล้ว" in content
    assert "แชร์เข้า LINE" in content
    assert "line.me/R/share?" in content
    assert roommate.full_name not in content
    assert roommate.origin_unit not in content
    assert roommate.phone not in content
    assert roommate.note not in content


def test_student_pass_keeps_owner_details_but_never_roommate_pii(client, ui4_setup):
    cohort = ui4_setup["cohort"]
    owner = ui4_setup["owner"]
    roommate = ui4_setup["roommate"]

    response = client.get(reverse("bookings:lodging_pass", args=[cohort.slug, owner.pk]))
    assert response.status_code == 200
    content = response.content.decode()

    assert owner.full_name in content
    assert "เตียง 2: มีผู้เข้าพักแล้ว" in content
    assert roommate.full_name not in content
    assert roommate.origin_unit not in content
    assert roommate.phone not in content
    assert roommate.note not in content
    assert owner.phone not in content
    assert owner.note not in content
    assert "คัดลอกลิงก์บัตร" in content
    assert "แชร์เข้า LINE" in content
    assert response["Cache-Control"] == "private, no-store, must-revalidate"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["X-Robots-Tag"] == "noindex, nofollow"


def test_checkin_masks_public_view_and_shows_full_details_only_to_supervisor(client, ui4_setup):
    owner = ui4_setup["owner"]
    public_url = reverse("bookings:lodging_checkin", args=[owner.pk])

    public = client.get(public_url)
    assert public.status_code == 200
    public_content = public.content.decode()
    assert "ข้อมูลถูกปกปิด" in public_content
    assert owner.full_name not in public_content
    assert owner.origin_unit not in public_content
    assert owner.phone not in public_content
    assert owner.note not in public_content
    assert "ยืนยันรายงานตัว" not in public_content

    client.force_login(ui4_setup["supervisor"])
    authorized = client.get(public_url)
    assert authorized.status_code == 200
    authorized_content = authorized.content.decode()
    assert "เจ้าหน้าที่รับรายงานตัว" in authorized_content
    assert owner.full_name in authorized_content
    assert owner.origin_unit in authorized_content
    assert owner.phone in authorized_content
    assert owner.note in authorized_content
    assert "ยืนยันรายงานตัว" in authorized_content


def test_manage_view_keeps_allocation_and_portal_status_separate(client, ui4_setup):
    client.force_login(ui4_setup["supervisor"])
    response = client.get(reverse("bookings:lodging_manage"))
    assert response.status_code == 200
    content = response.content.decode()

    assert "จัดสรรแล้ว" in content
    assert "เปิดรับจอง" in content
    assert "lodging-status-tags" in content


def test_force_release_danger_zone_is_superuser_only(client, ui4_setup):
    cohort = ui4_setup["cohort"]
    url = reverse("bookings:lodging_cohort_edit", args=[cohort.slug])

    client.force_login(ui4_setup["supervisor"])
    normal = client.get(url)
    assert normal.status_code == 200
    assert "Danger Zone" not in normal.content.decode()
    assert 'name="force_release"' not in normal.content.decode()

    client.force_login(ui4_setup["superuser"])
    admin = client.get(url)
    assert admin.status_code == 200
    admin_content = admin.content.decode()
    assert "Danger Zone" in admin_content
    assert 'name="force_release"' in admin_content
    assert 'name="release_reason"' in admin_content


def test_lodging_index_uses_semantic_progress_without_inline_capacity_width(client, ui4_setup):
    response = client.get(reverse("bookings:lodging_index"))
    assert response.status_code == 200
    content = response.content.decode()

    assert "lodging-capacity-progress" in content
    assert "lodging-capacity-fill" not in content
    assert 'role="progressbar"' not in content
    assert 'value="2"' in content
    assert 'max="4"' in content

"""UX-12 contracts for lodging cohort roster mobile clarity."""
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


def _template() -> str:
    return (Path(settings.BASE_DIR) / "templates" / "lodging" / "cohort_detail.html").read_text(encoding="utf-8")


def _css() -> str:
    return (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")


@pytest.fixture
def ux12_setup():
    unit = Unit.objects.create(code="UX12-UNIT", name="หน่วยทดสอบ UX-12")
    supervisor = User.objects.create_user(
        username="ux12_supervisor",
        email="ux12_supervisor@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.ต.",
        first_name="สมหวัง",
        last_name="ผู้กำกับ",
    )
    change_perm = Permission.objects.get(
        codename="change_courselodgingcohort", content_type__app_label="bookings"
    )
    permitted_user = User.objects.create_user(
        username="ux12_permitted",
        email="ux12_permitted@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.อ.",
        first_name="ผู้มีสิทธิ์",
        last_name="แก้ไข",
    )
    permitted_user.user_permissions.add(change_perm)

    staff_user = User.objects.create_user(
        username="ux12_staff",
        email="ux12_staff@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="จ.ส.อ.",
        first_name="สมศักดิ์",
        last_name="ผู้ตรวจ",
    )

    unrelated_user = User.objects.create_user(
        username="ux12_unrelated",
        email="ux12_unrelated@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.ท.",
        first_name="คนนอก",
        last_name="ไร้สิทธิ์",
    )

    superuser = User.objects.create_superuser(
        username="ux12_admin",
        email="ux12_admin@signalschool.ac.th",
        password="Password-2569",
    )

    room = Resource.objects.create(
        code="DORM-101",
        name="ห้องพัก 101",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
    )
    ResourceRule.objects.create(resource=room)

    start = timezone.localdate() + timedelta(days=7)
    end = start + timedelta(days=5)

    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรนายทหารสื่อสาร รุ่นที่ 12",
        slug="signal-officer-12",
        supervisor=supervisor,
        unit=unit,
        check_in_date=start,
        check_out_date=end,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
        beds_per_room=4,
    )
    cohort.rooms.add(room)

    now = timezone.now()
    student1 = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=1,
        rank="ร.อ.",
        full_name="เกียรติศักดิ์ สุขใจ",
        origin_unit="ศสส.ทบ.",
        phone="0811112233",
        checked_in_at=now,
        checked_in_by=staff_user,
    )

    student2 = CourseStudentLodging.objects.create(
        cohort=cohort,
        room=room,
        bed_number=2,
        rank="ร.ท.",
        full_name="อนันต์ มั่นคง",
        origin_unit="พัน.ส.ที่ 1",
        phone="0899998877",
    )

    return {
        "unit": unit,
        "supervisor": supervisor,
        "permitted_user": permitted_user,
        "staff_user": staff_user,
        "unrelated_user": unrelated_user,
        "superuser": superuser,
        "room": room,
        "cohort": cohort,
        "student1": student1,
        "student2": student2,
    }


@pytest.fixture
def ux12_setup_empty(ux12_setup):
    setup = ux12_setup
    empty_cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรที่ยังไม่มีนักเรียน",
        slug="empty-cohort-12",
        supervisor=setup["supervisor"],
        unit=setup["unit"],
        check_in_date=timezone.localdate() + timedelta(days=10),
        check_out_date=timezone.localdate() + timedelta(days=15),
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
        beds_per_room=4,
    )
    empty_cohort.rooms.add(setup["room"])
    return {**setup, "cohort_empty": empty_cohort}


def test_cohort_detail_template_has_single_semantic_roster_table():
    template = _template()
    assert template.count("<table") == 1
    assert template.count("lodging-roster-table") == 1
    assert "lodging-roster-wrap" in template
    assert "table-responsive-container" in template


def test_cohort_detail_template_preserves_exact_if_students_condition():
    template = _template()
    assert "{% if students %}" in template
    assert "{% endif %}" in template


def test_cohort_detail_template_includes_accessible_table_caption():
    template = _template()
    assert "<caption" in template
    assert "ทำเนียบรายชื่อผู้เข้าพักทั้งหมดในรอบหลักสูตร" in template
    assert "sr-only" in template


def test_cohort_detail_template_has_seven_exact_table_headers():
    template = _template()
    thead_content = template.split("<thead>", 1)[1].split("</thead>", 1)[0]
    for header in (
        "ลำดับ",
        "ห้อง / เตียง",
        "ยศ - ชื่อ - สกุล",
        "หน่วยต้นสังกัด",
        "เบอร์โทร",
        "เวลาที่ลงทะเบียน",
        "สถานะรายงานตัว",
    ):
        assert header in thead_content


def test_cohort_detail_template_cells_have_matching_data_labels():
    template = _template()
    tbody_content = template.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    for label in (
        'data-label="ลำดับ"',
        'data-label="ห้อง / เตียง"',
        'data-label="ยศ - ชื่อ - สกุล"',
        'data-label="หน่วยต้นสังกัด"',
        'data-label="เบอร์โทร"',
        'data-label="เวลาที่ลงทะเบียน"',
        'data-label="สถานะรายงานตัว"',
    ):
        assert label in tbody_content


def test_cohort_detail_template_has_roster_column_class_hooks():
    template = _template()
    for col_class in (
        "roster-col-order",
        "roster-col-room",
        "roster-col-name",
        "roster-col-unit",
        "roster-col-phone",
        "roster-col-time",
        "roster-col-status",
    ):
        assert col_class in template


def test_cohort_detail_template_has_roster_row_hook():
    template = _template()
    assert 'class="roster-row"' in template


def test_cohort_detail_template_has_export_cta_hook_and_csv_url():
    template = _template()
    assert "lodging-export-cta" in template
    assert "{% url 'bookings:lodging_cohort_export_csv' cohort.slug %}" in template
    assert "ส่งออก Excel / CSV" in template


def test_cohort_detail_template_preserves_share_banner_and_action_links():
    template = _template()
    assert "lodging-share-banner" in template
    assert "copyLinkBtn" in template
    assert "{{ share_url }}" in template
    assert "{{ line_share_url }}" in template
    assert "{{ qr_url }}" in template
    assert "{% url 'bookings:lodging_cohort_edit' cohort.slug %}" in template


def test_cohort_detail_template_preserves_copy_script_unchanged():
    template = _template()
    assert "function copyShareLink(url)" in template
    assert "navigator.clipboard.writeText(url)" in template
    assert "✓ คัดลอกสำเร็จ!" in template


def test_cohort_detail_view_anonymous_redirects_to_login(client, ux12_setup):
    cohort = ux12_setup["cohort"]
    response = client.get(reverse("bookings:lodging_cohort_detail", args=[cohort.slug]))
    assert response.status_code == 302
    assert "/login/" in response.url or reverse("accounts:login") in response.url


def test_cohort_detail_view_supervisor_returns_200(client, ux12_setup):
    client.force_login(ux12_setup["supervisor"])
    response = client.get(reverse("bookings:lodging_cohort_detail", args=[ux12_setup["cohort"].slug]))
    assert response.status_code == 200


def test_cohort_detail_view_superuser_returns_200(client, ux12_setup):
    client.force_login(ux12_setup["superuser"])
    response = client.get(reverse("bookings:lodging_cohort_detail", args=[ux12_setup["cohort"].slug]))
    assert response.status_code == 200


def test_cohort_detail_view_permitted_user_returns_200(client, ux12_setup):
    client.force_login(ux12_setup["permitted_user"])
    response = client.get(reverse("bookings:lodging_cohort_detail", args=[ux12_setup["cohort"].slug]))
    assert response.status_code == 200


def test_cohort_detail_view_unrelated_user_returns_403(client, ux12_setup):
    client.force_login(ux12_setup["unrelated_user"])
    response = client.get(reverse("bookings:lodging_cohort_detail", args=[ux12_setup["cohort"].slug]))
    assert response.status_code == 403


def test_cohort_detail_view_renders_single_roster_table_when_students_present(client, ux12_setup):
    client.force_login(ux12_setup["supervisor"])
    response = client.get(reverse("bookings:lodging_cohort_detail", args=[ux12_setup["cohort"].slug]))
    html = response.content.decode("utf-8")
    assert response.status_code == 200
    assert html.count("<table") == 1
    assert "lodging-roster-table" in html


def test_cohort_detail_view_renders_all_seven_student_data_values(client, ux12_setup):
    client.force_login(ux12_setup["supervisor"])
    response = client.get(reverse("bookings:lodging_cohort_detail", args=[ux12_setup["cohort"].slug]))
    html = response.content.decode("utf-8")
    assert "เกียรติศักดิ์ สุขใจ" in html
    assert "ศสส.ทบ." in html
    assert "DORM-101" in html
    assert "เตียง 1" in html
    assert "0811112233" in html
    assert "อนันต์ มั่นคง" in html
    assert "พัน.ส.ที่ 1" in html
    assert "0899998877" in html


def test_cohort_detail_view_renders_checked_in_metadata_and_staff_name(client, ux12_setup):
    client.force_login(ux12_setup["supervisor"])
    response = client.get(reverse("bookings:lodging_cohort_detail", args=[ux12_setup["cohort"].slug]))
    html = response.content.decode("utf-8")
    assert "✓" in html
    assert ux12_setup["staff_user"].display_name in html


def test_cohort_detail_view_renders_unchecked_in_dash(client, ux12_setup):
    client.force_login(ux12_setup["supervisor"])
    response = client.get(reverse("bookings:lodging_cohort_detail", args=[ux12_setup["cohort"].slug]))
    html = response.content.decode("utf-8")
    assert '<span class="muted-text">-</span>' in html


def test_cohort_detail_view_omits_roster_table_when_no_students(client, ux12_setup_empty):
    client.force_login(ux12_setup_empty["supervisor"])
    response = client.get(reverse("bookings:lodging_cohort_detail", args=[ux12_setup_empty["cohort_empty"].slug]))
    html = response.content.decode("utf-8")
    assert response.status_code == 200
    assert "lodging-roster-table" not in html
    assert "<table" not in html


def test_ux12_css_marker_present_in_stylesheet():
    css = _css()
    assert "/* UX-12 Lodging Cohort Roster Mobile Clarity */" in css


def test_ux12_css_uses_exact_mobile_breakpoint_47_99rem():
    css = _css()
    marker = "/* UX-12 Lodging Cohort Roster Mobile Clarity */"
    ux12_css = css.split(marker, 1)[1]
    assert "@media (max-width: 47.99rem)" in ux12_css
    assert "@media (max-width: 48rem)" not in ux12_css


def test_ux12_css_has_no_has_selector():
    css = _css()
    marker = "/* UX-12 Lodging Cohort Roster Mobile Clarity */"
    ux12_css = css.split(marker, 1)[1]
    assert ":has(" not in ux12_css


def test_ux12_css_scopes_table_and_wrap_with_overflow_and_min_width_reset():
    css = _css()
    marker = "/* UX-12 Lodging Cohort Roster Mobile Clarity */"
    ux12_css = css.split(marker, 1)[1]
    assert ".lodging-roster-wrap" in ux12_css
    assert ".lodging-roster-wrap .lodging-roster-table" in ux12_css
    assert "overflow: visible" in ux12_css
    assert "min-width: 0" in ux12_css


def test_ux12_css_hides_thead_accessibly():
    css = _css()
    marker = "/* UX-12 Lodging Cohort Roster Mobile Clarity */"
    ux12_css = css.split(marker, 1)[1]
    assert ".lodging-roster-table thead" in ux12_css
    assert "position: absolute" in ux12_css
    assert "clip: rect(0 0 0 0)" in ux12_css
    assert "clip-path: inset(50%)" in ux12_css


def test_ux12_css_formats_card_rows_and_uses_data_label_content():
    css = _css()
    marker = "/* UX-12 Lodging Cohort Roster Mobile Clarity */"
    ux12_css = css.split(marker, 1)[1]
    assert ".lodging-roster-table .roster-row" in ux12_css
    assert "display: grid" in ux12_css
    assert "content: attr(data-label)" in ux12_css


def test_ux12_css_enforces_wrap_safe_wrapping_properties():
    css = _css()
    marker = "/* UX-12 Lodging Cohort Roster Mobile Clarity */"
    ux12_css = css.split(marker, 1)[1]
    assert "overflow-wrap: anywhere" in ux12_css
    assert "word-break: break-word" in ux12_css
    assert ".roster-col-order" in ux12_css
    assert ".roster-col-status" in ux12_css


def test_ux12_css_enforces_export_cta_touch_target_and_full_width():
    css = _css()
    marker = "/* UX-12 Lodging Cohort Roster Mobile Clarity */"
    ux12_css = css.split(marker, 1)[1]
    assert ".lodging-export-cta" in ux12_css
    assert "width: 100%" in ux12_css
    assert "min-height: 44px" in ux12_css

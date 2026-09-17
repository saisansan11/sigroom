"""UX-14 contracts for lodging cohort edit mobile clarity, semantics, and accessibility."""
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import Permission
from django.urls import resolve, reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


def _template() -> str:
    return (Path(settings.BASE_DIR) / "templates" / "lodging" / "cohort_edit.html").read_text(encoding="utf-8")


def _css() -> str:
    return (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")


def _ux14_css() -> str:
    css = _css()
    marker = "/* UX-14 Lodging Cohort Edit Mobile Clarity */"
    assert marker in css, "UX-14 marker must exist in app.css"
    return css.split(marker, 1)[1]


@pytest.fixture
def ux14_setup():
    unit = Unit.objects.create(code="UX14-UNIT", name="หน่วยทดสอบแก้ไขรอบที่พัก UX-14")

    supervisor = User.objects.create_user(
        username="ux14_supervisor",
        email="ux14_supervisor@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.ต.",
        first_name="ประสิทธิ์",
        last_name="ผู้กำกับรุ่น",
    )

    change_perm = Permission.objects.get(
        codename="change_courselodgingcohort", content_type__app_label="bookings"
    )

    permitted_user = User.objects.create_user(
        username="ux14_permitted",
        email="ux14_permitted@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.ท.",
        first_name="สมเกียรติ",
        last_name="ผู้มีสิทธิ์แก้ไข",
    )
    permitted_user.user_permissions.add(change_perm)

    unrelated_user = User.objects.create_user(
        username="ux14_unrelated",
        email="ux14_unrelated@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.อ.",
        first_name="มนตรี",
        last_name="ไร้สิทธิ์แก้ไข",
    )

    superuser = User.objects.create_superuser(
        username="ux14_admin",
        email="ux14_admin@signalschool.ac.th",
        password="Password-2569",
    )

    room1 = Resource.objects.create(
        code="DORM-301",
        name="ห้องพัก 301",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
        status=Resource.Status.ACTIVE,
    )
    ResourceRule.objects.create(resource=room1)

    room2 = Resource.objects.create(
        code="DORM-302",
        name="ห้องพัก 302",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
        status=Resource.Status.ACTIVE,
    )
    ResourceRule.objects.create(resource=room2)

    start = timezone.localdate() + timedelta(days=10)
    end = start + timedelta(days=14)

    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรการปฏิบัติการร่วมทางสัญญาณและสารสนเทศ รุ่นที่ 18",
        slug="joint-sig-18",
        supervisor=supervisor,
        unit=unit,
        check_in_date=start,
        check_out_date=end,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
        beds_per_room=4,
        note="ผู้เข้ารับการอบรมกรุณาเตรียมเครื่องแต่งกายฝึก",
    )
    cohort.rooms.add(room1)

    return {
        "unit": unit,
        "supervisor": supervisor,
        "permitted_user": permitted_user,
        "unrelated_user": unrelated_user,
        "superuser": superuser,
        "room1": room1,
        "room2": room2,
        "cohort": cohort,
    }


# ==============================================================================
# 1. Template Structure, Semantics & Script Tests
# ==============================================================================

def test_cohort_edit_template_uses_semantic_fieldset_and_legend():
    template = _template()
    assert "<fieldset" in template
    assert 'class="lodging-room-fieldset"' in template
    assert "<legend>ห้องพักที่จัดสรรในรอบนี้</legend>" in template


def test_cohort_edit_template_does_not_nest_labels_in_room_checklist():
    template = _template()
    # Old template had: <label>ห้องพักที่จัดสรรในรอบนี้ \n <div class="lodging-room-checklist">
    assert "<label>ห้องพักที่จัดสรรในรอบนี้" not in template


def test_cohort_edit_template_preserves_exact_rooms_input_name_and_values():
    template = _template()
    assert 'name="rooms"' in template
    assert 'value="{{ room.pk }}"' in template
    assert '{% if room in cohort.rooms.all %}checked{% endif %}' in template


def test_cohort_edit_template_has_accessible_select_all_and_deselect_all_controls():
    template = _template()
    assert "lodging-room-selection-tools" in template
    assert "lodging-selection-btn" in template
    assert "เลือกทั้งหมด" in template
    assert "ยกเลิกทั้งหมด" in template
    assert "setRoomCheckboxes(true)" in template
    assert "setRoomCheckboxes(false)" in template
    assert 'role="group"' in template


def test_cohort_edit_template_selection_script_scopes_strictly_to_room_checkboxes():
    template = _template()
    assert "function setRoomCheckboxes(checked)" in template
    assert "querySelector('.lodging-edit-card .lodging-room-checklist')" in template
    assert 'input[type="checkbox"][name="rooms"]' in template


def test_cohort_edit_template_preserves_all_form_field_names():
    template = _template()
    assert 'name="title"' in template
    assert 'name="check_in_date"' in template
    assert 'name="check_out_date"' in template
    assert 'name="allocation_status"' in template
    assert 'name="beds_per_room"' in template
    assert 'name="is_active"' in template
    assert 'name="rooms"' in template
    assert 'name="note"' in template
    assert 'name="force_release"' in template
    assert 'name="release_reason"' in template


def test_cohort_edit_template_has_action_hierarchy():
    template = _template()
    assert "lodging-edit-actions" in template
    assert "ยกเลิก" in template
    assert "บันทึกการเปลี่ยนแปลง" in template


# ==============================================================================
# 2. Permission Boundary & Superuser Danger Zone Tests
# ==============================================================================

def test_cohort_edit_anonymous_redirects_to_login(client, ux14_setup):
    url = reverse("bookings:lodging_cohort_edit", args=[ux14_setup["cohort"].slug])
    response = client.get(url)
    assert response.status_code == 302
    assert "/login/" in response.url or reverse("accounts:login") in response.url


def test_cohort_edit_unrelated_user_returns_403(client, ux14_setup):
    client.force_login(ux14_setup["unrelated_user"])
    url = reverse("bookings:lodging_cohort_edit", args=[ux14_setup["cohort"].slug])
    response = client.get(url)
    assert response.status_code == 403


def test_cohort_edit_supervisor_sees_form_without_danger_zone(client, ux14_setup):
    client.force_login(ux14_setup["supervisor"])
    url = reverse("bookings:lodging_cohort_edit", args=[ux14_setup["cohort"].slug])
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "แก้ไขรอบที่พัก" in html
    assert ux14_setup["cohort"].title in html
    assert "ห้องพักที่จัดสรรในรอบนี้" in html
    assert "เลือกทั้งหมด" in html
    assert "ยกเลิกทั้งหมด" in html
    # Normal supervisor must NOT see danger zone
    assert "Danger Zone" not in html
    assert 'name="force_release"' not in html
    assert 'name="release_reason"' not in html


def test_cohort_edit_permitted_user_sees_form_without_danger_zone(client, ux14_setup):
    client.force_login(ux14_setup["permitted_user"])
    url = reverse("bookings:lodging_cohort_edit", args=[ux14_setup["cohort"].slug])
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "แก้ไขรอบที่พัก" in html
    assert "Danger Zone" not in html
    assert 'name="force_release"' not in html


def test_cohort_edit_superuser_sees_danger_zone(client, ux14_setup):
    client.force_login(ux14_setup["superuser"])
    url = reverse("bookings:lodging_cohort_edit", args=[ux14_setup["cohort"].slug])
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "Danger Zone" in html
    assert "เขตการดำเนินการพิเศษ (Danger Zone) — บังคับปลดการสงวนห้องพัก" in html
    assert 'name="force_release"' in html
    assert 'name="release_reason"' in html


# ==============================================================================
# 3. Form POST Contract Tests
# ==============================================================================

def test_cohort_edit_post_by_supervisor_updates_cohort_and_rooms(client, ux14_setup):
    client.force_login(ux14_setup["supervisor"])
    cohort = ux14_setup["cohort"]
    url = reverse("bookings:lodging_cohort_edit", args=[cohort.slug])

    new_start = cohort.check_in_date + timedelta(days=2)
    new_end = cohort.check_out_date + timedelta(days=2)

    response = client.post(
        url,
        {
            "title": "หลักสูตรการปฏิบัติการร่วมทางสัญญาณและสารสนเทศ รุ่นที่ 18 (แก้ไข)",
            "check_in_date": new_start.isoformat(),
            "check_out_date": new_end.isoformat(),
            "allocation_status": CourseLodgingCohort.AllocationStatus.ALLOCATED,
            "beds_per_room": 3,
            "is_active": "1",
            "rooms": [str(ux14_setup["room1"].pk), str(ux14_setup["room2"].pk)],
            "note": "ปรับเวลาเข้าพักเป็น 17:00 น.",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("bookings:lodging_cohort_detail", args=[cohort.slug])

    cohort.refresh_from_db()
    assert cohort.title == "หลักสูตรการปฏิบัติการร่วมทางสัญญาณและสารสนเทศ รุ่นที่ 18 (แก้ไข)"
    assert cohort.check_in_date == new_start
    assert cohort.check_out_date == new_end
    assert cohort.beds_per_room == 3
    assert cohort.is_active is True
    assert set(cohort.rooms.values_list("pk", flat=True)) == {
        ux14_setup["room1"].pk,
        ux14_setup["room2"].pk,
    }
    assert cohort.note == "ปรับเวลาเข้าพักเป็น 17:00 น."


def test_cohort_edit_post_by_unrelated_user_returns_403(client, ux14_setup):
    client.force_login(ux14_setup["unrelated_user"])
    url = reverse("bookings:lodging_cohort_edit", args=[ux14_setup["cohort"].slug])
    response = client.post(
        url,
        {
            "title": "เจาะระบบแก้ไขข้อมูล",
            "check_in_date": ux14_setup["cohort"].check_in_date.isoformat(),
            "check_out_date": ux14_setup["cohort"].check_out_date.isoformat(),
            "beds_per_room": 4,
            "rooms": [str(ux14_setup["room1"].pk)],
        },
    )
    assert response.status_code == 403


def test_cohort_edit_post_by_superuser_with_force_release(client, ux14_setup):
    client.force_login(ux14_setup["superuser"])
    cohort = ux14_setup["cohort"]
    url = reverse("bookings:lodging_cohort_edit", args=[cohort.slug])

    response = client.post(
        url,
        {
            "title": cohort.title,
            "check_in_date": cohort.check_in_date.isoformat(),
            "check_out_date": cohort.check_out_date.isoformat(),
            "allocation_status": CourseLodgingCohort.AllocationStatus.RELEASED,
            "beds_per_room": cohort.beds_per_room,
            "rooms": [],
            "force_release": "1",
            "release_reason": "ยกเลิกหลักสูตรเนื่องจากภารกิจด่วนพิเศษ",
        },
    )
    assert response.status_code == 302
    cohort.refresh_from_db()
    assert cohort.allocation_status == CourseLodgingCohort.AllocationStatus.RELEASED
    assert cohort.rooms.count() == 0


def test_cohort_edit_post_invalid_dates_renders_error(client, ux14_setup):
    client.force_login(ux14_setup["supervisor"])
    cohort = ux14_setup["cohort"]
    url = reverse("bookings:lodging_cohort_edit", args=[cohort.slug])

    # End date before start date
    invalid_end = cohort.check_in_date - timedelta(days=1)
    response = client.post(
        url,
        {
            "title": cohort.title,
            "check_in_date": cohort.check_in_date.isoformat(),
            "check_out_date": invalid_end.isoformat(),
            "beds_per_room": 4,
            "rooms": [str(ux14_setup["room1"].pk)],
        },
    )
    assert response.status_code == 200
    html = response.content.decode("utf-8")
    assert "ไม่สามารถบันทึกการเปลี่ยนแปลงได้" in html


# ==============================================================================
# 4. CSS Contracts Tests
# ==============================================================================

def test_ux14_css_marker_present_in_stylesheet():
    css = _css()
    assert "/* UX-14 Lodging Cohort Edit Mobile Clarity */" in css


def test_ux14_css_uses_exact_mobile_breakpoint_47_99rem():
    ux14 = _ux14_css()
    assert "@media (max-width: 47.99rem)" in ux14
    assert "@media (max-width: 48rem)" not in ux14


def test_ux14_css_has_no_has_selector():
    ux14 = _ux14_css()
    assert ":has(" not in ux14


def test_ux14_css_enforces_grid_dates_one_column_below_48rem():
    ux14 = _ux14_css()
    mobile_block = ux14.split("@media (max-width: 47.99rem)", 1)[1]
    assert ".lodging-edit-card .grid-dates" in mobile_block
    assert "grid-template-columns: 1fr;" in mobile_block


def test_ux14_css_enforces_form_actions_mobile_contracts():
    ux14 = _ux14_css()
    assert ".lodging-edit-card .form-actions button" in ux14
    assert ".lodging-edit-card .form-actions a[role=\"button\"]" in ux14
    assert "min-height: 44px" in ux14
    mobile_block = ux14.split("@media (max-width: 47.99rem)", 1)[1]
    assert ".lodging-edit-card .form-actions" in mobile_block
    assert "width: 100%" in mobile_block
    assert "grid-template-columns: 1fr;" in mobile_block


def test_ux14_css_enforces_touch_target_and_focus_for_checkbox_labels():
    ux14 = _ux14_css()
    assert ".lodging-edit-card .lodging-checkbox-label" in ux14
    assert "min-height: 44px" in ux14
    assert ".lodging-edit-card .lodging-checkbox-label:focus-within" in ux14
    assert '.lodging-edit-card .lodging-checkbox-label input[type="checkbox"]:focus-visible' in ux14


def test_ux14_css_enforces_safe_wrapping_and_danger_zone_readability():
    ux14 = _ux14_css()
    assert ".lodging-danger-header" in ux14
    assert ".lodging-danger-warning" in ux14
    assert "overflow-wrap: anywhere" in ux14
    assert "word-break: break-word" in ux14
    mobile_block = ux14.split("@media (max-width: 47.99rem)", 1)[1]
    assert ".lodging-danger-zone" in mobile_block
    assert "padding: var(--space-md);" in mobile_block


# ==============================================================================
# 5. Invariant Protection: No URL, View, Model or Service Changes
# ==============================================================================

def test_url_resolves_to_lodging_cohort_edit_view():
    match = resolve("/lodging/cohorts/test-slug/edit/")
    assert match.view_name == "bookings:lodging_cohort_edit"
    assert match.func.__name__ == "lodging_cohort_edit"

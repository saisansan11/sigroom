"""UX-13 contracts for lodging cohort management mobile clarity and semantics."""
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


def _template() -> str:
    return (Path(settings.BASE_DIR) / "templates" / "lodging" / "manage_list.html").read_text(encoding="utf-8")


def _css() -> str:
    return (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")


def _ux13_css() -> str:
    css = _css()
    marker = "/* UX-13 Lodging Cohort Management Mobile Clarity */"
    assert marker in css, "UX-13 marker must exist in app.css"
    return css.split(marker, 1)[1]


@pytest.fixture
def ux13_setup():
    unit = Unit.objects.create(code="UX13-UNIT", name="หน่วยทดสอบ UX-13")

    supervisor = User.objects.create_user(
        username="ux13_supervisor",
        email="ux13_supervisor@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.ต.",
        first_name="ประสิทธิ์",
        last_name="ผู้กำกับ",
    )

    add_perm = Permission.objects.get(
        codename="add_courselodgingcohort", content_type__app_label="bookings"
    )
    change_perm = Permission.objects.get(
        codename="change_courselodgingcohort", content_type__app_label="bookings"
    )

    permitted_creator = User.objects.create_user(
        username="ux13_creator",
        email="ux13_creator@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.ท.",
        first_name="สมเกียรติ",
        last_name="ผู้สร้าง",
    )
    permitted_creator.user_permissions.add(add_perm, change_perm)

    unrelated_user = User.objects.create_user(
        username="ux13_unrelated",
        email="ux13_unrelated@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.อ.",
        first_name="มนตรี",
        last_name="ไร้สิทธิ์",
    )

    superuser = User.objects.create_superuser(
        username="ux13_admin",
        email="ux13_admin@signalschool.ac.th",
        password="Password-2569",
    )

    room1 = Resource.objects.create(
        code="DORM-201",
        name="ห้องพัก 201",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
        status=Resource.Status.ACTIVE,
    )
    ResourceRule.objects.create(resource=room1)

    room2 = Resource.objects.create(
        code="DORM-202",
        name="ห้องพัก 202",
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        capacity=4,
        status=Resource.Status.ACTIVE,
    )
    ResourceRule.objects.create(resource=room2)

    start = timezone.localdate() + timedelta(days=14)
    end = start + timedelta(days=7)

    cohort = CourseLodgingCohort.objects.create(
        title="หลักสูตรนายทหารสื่อสารระดับผู้บังคับบัญชาและฝ่ายอำนวยการเพื่อความมั่นคงแห่งชาติ รุ่นที่ 70",
        slug="cmd-comm-70",
        supervisor=supervisor,
        unit=unit,
        check_in_date=start,
        check_out_date=end,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
        beds_per_room=4,
    )
    cohort.rooms.add(room1)

    return {
        "unit": unit,
        "supervisor": supervisor,
        "permitted_creator": permitted_creator,
        "unrelated_user": unrelated_user,
        "superuser": superuser,
        "room1": room1,
        "room2": room2,
        "cohort": cohort,
    }


# ==============================================================================
# 1. Template Structure, Semantics & Script Tests
# ==============================================================================

def test_manage_template_uses_semantic_fieldset_and_legend():
    template = _template()
    assert "<fieldset" in template
    assert 'class="lodging-room-fieldset"' in template
    assert "<legend>เลือกห้องพักที่เปิดให้จองในรอบนี้</legend>" in template


def test_manage_template_does_not_nest_labels_in_room_checklist():
    template = _template()
    # The old template had: <label>เลือกห้องพักที่เปิดให้จองในรอบนี้ \n <div class="lodging-room-checklist"> ... <label class="lodging-checklist-item">
    # Verify the outer label pattern is completely eliminated
    assert "<label>เลือกห้องพักที่เปิดให้จองในรอบนี้" not in template


def test_manage_template_preserves_exact_rooms_input_name():
    template = _template()
    assert 'name="rooms"' in template
    assert 'value="{{ rm.id }}"' in template


def test_manage_template_has_accessible_select_all_and_deselect_all_controls():
    template = _template()
    assert "lodging-room-selection-tools" in template
    assert "lodging-selection-btn" in template
    assert "เลือกทั้งหมด" in template
    assert "ยกเลิกทั้งหมด" in template
    assert "setRoomCheckboxes(true)" in template
    assert "setRoomCheckboxes(false)" in template
    assert 'role="group"' in template


def test_manage_template_selection_script_scopes_strictly_to_room_checkboxes():
    template = _template()
    assert "function setRoomCheckboxes(checked)" in template
    assert "querySelector('.lodging-room-checklist')" in template
    assert 'input[type="checkbox"][name="rooms"]' in template


def test_manage_template_has_direct_student_portal_affordances_on_cards():
    template = _template()
    assert "{% url 'bookings:lodging_portal' c.slug as portal_url %}" in template
    # Primary action
    assert "lodging-card-primary-action" in template
    assert "{% url 'bookings:lodging_cohort_detail' c.slug %}" in template
    assert "ดูรายชื่อนักเรียน →" in template
    # Direct copy button
    assert "lodging-copy-btn" in template
    assert "data-portal-path=" in template
    assert "onclick=\"copyCohortLink(this)\"" in template
    assert "📋 คัดลอกลิงก์" in template
    # Direct LINE share
    assert "lodging-line-share-btn" in template
    assert "line.me/R/share?" in template
    assert "แชร์ผ่าน LINE ↗" in template
    assert 'target="_blank"' in template
    assert 'rel="noopener noreferrer"' in template
    # Direct student portal open & edit
    assert "lodging-portal-link" in template
    assert "เปิดหน้านักเรียน ↗" in template
    assert "lodging-edit-link" in template
    assert "แก้ไข" in template


def test_manage_template_copy_script_provides_feedback_and_fallback():
    template = _template()
    assert "function copyCohortLink(btn)" in template
    assert "navigator.clipboard.writeText" in template
    assert "✓ คัดลอกสำเร็จ!" in template
    assert "is-copied" in template
    # Fallback when clipboard API is unavailable / non-secure context
    assert "document.execCommand('copy')" in template or "prompt(" in template


def test_manage_template_omits_out_of_scope_quick_jump_task_bar():
    template = _template()
    assert "quick-jump" not in template
    assert "task-bar" not in template
    assert "lodging-task-bar" not in template


# ==============================================================================
# 2. Permission Boundary & can_create Tests
# ==============================================================================

def test_manage_view_anonymous_redirects_to_login(client):
    response = client.get(reverse("bookings:lodging_manage"))
    assert response.status_code == 302
    assert "/login/" in response.url or reverse("accounts:login") in response.url


def test_manage_view_permitted_creator_has_can_create_true(client, ux13_setup):
    client.force_login(ux13_setup["permitted_creator"])
    response = client.get(reverse("bookings:lodging_manage"))
    assert response.status_code == 200
    assert response.context["can_create"] is True
    html = response.content.decode("utf-8")
    assert "เปิดรอบจองที่พักให้นักเรียน" in html
    assert 'class="lodging-room-fieldset"' in html
    assert "เลือกทั้งหมด" in html
    assert "ยกเลิกทั้งหมด" in html


def test_manage_view_superuser_has_can_create_true(client, ux13_setup):
    client.force_login(ux13_setup["superuser"])
    response = client.get(reverse("bookings:lodging_manage"))
    assert response.status_code == 200
    assert response.context["can_create"] is True
    html = response.content.decode("utf-8")
    assert "เปิดรอบจองที่พักให้นักเรียน" in html


def test_manage_view_assigned_supervisor_without_create_perm_sees_cohorts_but_no_form(client, ux13_setup):
    client.force_login(ux13_setup["supervisor"])
    response = client.get(reverse("bookings:lodging_manage"))
    assert response.status_code == 200
    assert response.context["can_create"] is False
    html = response.content.decode("utf-8")
    # Supervisor sees their assigned cohort
    assert ux13_setup["cohort"].title in html
    assert "📋 คัดลอกลิงก์" in html
    assert "แชร์ผ่าน LINE ↗" in html
    # But does NOT see create form
    assert "เปิดรอบจองที่พักให้นักเรียน" not in html
    assert "คุณเป็นผู้กำกับหลักสูตรและดูแลรุ่นที่ได้รับมอบหมายได้ แต่ไม่มีสิทธิ์สร้างรอบใหม่" in html


def test_manage_view_unrelated_user_without_permission_or_cohorts_returns_403(client, ux13_setup):
    client.force_login(ux13_setup["unrelated_user"])
    response = client.get(reverse("bookings:lodging_manage"))
    assert response.status_code == 403


def test_manage_view_supervisor_with_no_cohorts_sees_empty_state(client, ux13_setup):
    # User with change permission has management access but cannot create if lacking add permission
    change_perm = Permission.objects.get(
        codename="change_courselodgingcohort", content_type__app_label="bookings"
    )
    manager = User.objects.create_user(
        username="ux13_manager_empty",
        email="ux13_manager_empty@signalschool.ac.th",
        password="Password-2569",
        unit=ux13_setup["unit"],
        rank="ร.อ.",
        first_name="ผู้จัดการ",
        last_name="ว่างเปล่า",
    )
    manager.user_permissions.add(change_perm)
    # Remove all cohorts
    CourseLodgingCohort.objects.all().delete()

    client.force_login(manager)
    response = client.get(reverse("bookings:lodging_manage"))
    assert response.status_code == 200
    assert response.context["can_create"] is False
    html = response.content.decode("utf-8")
    assert "ยังไม่มีรอบการจองที่สร้างไว้" in html
    assert "เปิดรอบจองที่พักให้นักเรียน" not in html



def test_manage_view_post_by_user_without_create_perm_raises_403(client, ux13_setup):
    client.force_login(ux13_setup["supervisor"])
    start = timezone.localdate() + timedelta(days=20)
    end = start + timedelta(days=5)
    response = client.post(
        reverse("bookings:lodging_manage"),
        {
            "title": "รอบทดสอบไม่มีสิทธิ์สร้าง",
            "slug": "unauthorized-cohort",
            "check_in_date": start.isoformat(),
            "check_out_date": end.isoformat(),
            "beds_per_room": 4,
            "rooms": [str(ux13_setup["room2"].pk)],
        },
    )
    assert response.status_code == 403


def test_manage_view_post_by_permitted_creator_creates_cohort_with_rooms(client, ux13_setup):
    client.force_login(ux13_setup["permitted_creator"])
    start = timezone.localdate() + timedelta(days=30)
    end = start + timedelta(days=10)
    response = client.post(
        reverse("bookings:lodging_manage"),
        {
            "title": "หลักสูตรนายสิบสื่อสาร รุ่นที่ 45",
            "slug": "nco-comm-45",
            "check_in_date": start.isoformat(),
            "check_out_date": end.isoformat(),
            "beds_per_room": 4,
            "rooms": [str(ux13_setup["room2"].pk)],
            "note": "เตรียมอุปกรณ์เครื่องนอนส่วนตัว",
        },
    )
    assert response.status_code == 302
    created = CourseLodgingCohort.objects.get(slug="nco-comm-45")
    assert created.title == "หลักสูตรนายสิบสื่อสาร รุ่นที่ 45"
    assert created.allocation_status == CourseLodgingCohort.AllocationStatus.ALLOCATED
    assert created.is_active is True
    assert list(created.rooms.values_list("pk", flat=True)) == [ux13_setup["room2"].pk]


def test_manage_view_renders_line_share_and_copy_affordances_on_cohort_card(client, ux13_setup):
    client.force_login(ux13_setup["supervisor"])
    response = client.get(reverse("bookings:lodging_manage"))
    html = response.content.decode("utf-8")
    assert response.status_code == 200
    cohort = ux13_setup["cohort"]
    assert cohort.title in html
    assert f'data-portal-path="/lodging/c/{cohort.slug}/"' in html
    assert "https://line.me/R/share?text=" in html
    assert "📋 คัดลอกลิงก์" in html
    assert "แชร์ผ่าน LINE ↗" in html
    assert "ดูรายชื่อนักเรียน →" in html


# ==============================================================================
# 3. CSS Contracts Tests
# ==============================================================================

def test_ux13_css_marker_present_in_stylesheet():
    css = _css()
    assert "/* UX-13 Lodging Cohort Management Mobile Clarity */" in css


def test_ux13_css_uses_exact_mobile_breakpoint_47_99rem():
    ux13 = _ux13_css()
    assert "@media (max-width: 47.99rem)" in ux13
    assert "@media (max-width: 48rem)" not in ux13


def test_ux13_css_has_no_has_selector():
    ux13 = _ux13_css()
    assert ":has(" not in ux13


def test_ux13_css_resets_fieldset_and_legend_semantics_neutrally():
    ux13 = _ux13_css()
    assert ".lodging-room-fieldset" in ux13
    assert ".lodging-room-fieldset > legend" in ux13


def test_ux13_css_enforces_checklist_item_touch_target_and_focus():
    ux13 = _ux13_css()
    assert ".lodging-room-fieldset .lodging-checklist-item" in ux13
    assert "min-height: 44px" in ux13
    assert ".lodging-room-fieldset .lodging-checklist-item:focus-within" in ux13
    assert '.lodging-room-fieldset .lodging-checklist-item input[type="checkbox"]:focus-visible' in ux13
    assert "\n.lodging-checklist-item {" not in ux13
    assert "\n.lodging-checklist-item:focus-within" not in ux13
    assert '\n.lodging-checklist-item input[type="checkbox"]:focus-visible' not in ux13


def test_ux13_css_enforces_card_actions_mobile_contracts():
    ux13 = _ux13_css()
    assert ".lodging-manage-card-actions .lodging-card-primary-action" in ux13
    assert "width: 100%" in ux13
    assert "min-height: 44px" in ux13
    assert ".lodging-manage-card-actions a[role=\"button\"].secondary" in ux13
    assert ".lodging-manage-card-actions button.secondary" in ux13


def test_ux13_css_enforces_grid_dates_one_column_below_48rem():
    ux13 = _ux13_css()
    mobile_block = ux13.split("@media (max-width: 47.99rem)", 1)[1]
    assert ".lodging-manage-grid .grid-dates" in mobile_block
    assert "grid-template-columns: 1fr;" in mobile_block
    assert "\n  .grid-dates {" not in mobile_block


def test_ux13_css_enforces_safe_wrapping_for_thai_title_and_tags():
    ux13 = _ux13_css()
    assert ".lodging-manage-card-head h3" in ux13
    assert "overflow-wrap: anywhere" in ux13
    assert "word-break: break-word" in ux13
    assert ".lodging-status-tags span" in ux13
    assert "white-space: normal" in ux13


def test_ux13_css_enforces_selection_tools_styling_and_touch_target():
    ux13 = _ux13_css()
    assert ".lodging-room-selection-tools" in ux13
    assert ".lodging-selection-btn" in ux13
    mobile_block = ux13.split("@media (max-width: 47.99rem)", 1)[1]
    assert ".lodging-selection-btn" in mobile_block
    assert "min-height: 44px" in mobile_block

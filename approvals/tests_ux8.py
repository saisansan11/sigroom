"""UX-8 contracts for approver delegation mobile clarity."""
from datetime import timedelta
from pathlib import Path
import re

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from approvals.models import ApproverDelegation
from resources.models import Resource, ResourceApprover


pytestmark = pytest.mark.django_db


@pytest.fixture
def delegation_page_setup():
    unit = Unit.objects.create(code="HQ-UX8", name="กองบังคับการ UX-8")
    primary_approver = User.objects.create_user(
        username="ux8-primary",
        email="ux8-primary@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.อ.",
        first_name="สมศักดิ์",
        last_name="หลักดี",
    )
    backup_approver = User.objects.create_user(
        username="ux8-backup",
        email="ux8-backup@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.ท.",
        first_name="สมเกียรติ",
        last_name="รองดี",
    )
    delegate_user = User.objects.create_user(
        username="ux8-delegate",
        email="ux8-delegate@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.ต.",
        first_name="ประสิทธิ์",
        last_name="แทนดี",
    )
    other_primary = User.objects.create_user(
        username="ux8-other-primary",
        email="ux8-other-primary@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.อ.",
        first_name="วันชัย",
        last_name="คนอื่น",
    )
    outsider = User.objects.create_user(
        username="ux8-outsider",
        email="ux8-outsider@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    room = Resource.objects.create(code="UX8-ROOM", name="ห้องทดสอบ UX-8")
    other_room = Resource.objects.create(code="UX8-ROOM-2", name="ห้องทดสอบ UX-8 (2)")
    ResourceApprover.objects.create(resource=room, user=primary_approver, is_primary=True)
    ResourceApprover.objects.create(resource=room, user=backup_approver, is_primary=False)
    ResourceApprover.objects.create(resource=other_room, user=other_primary, is_primary=True)
    return {
        "primary": primary_approver,
        "backup": backup_approver,
        "delegate": delegate_user,
        "other_primary": other_primary,
        "outsider": outsider,
        "room": room,
        "other_room": other_room,
    }


def test_delegation_template_keeps_one_semantic_table_and_responsive_hooks():
    template = (Path(settings.BASE_DIR) / "templates" / "approvals" / "delegation.html").read_text(encoding="utf-8")

    assert template.count('<table class="delegation-table">') == 1
    assert "<thead>" in template
    assert "<th>ผู้รักษาการ</th>" in template
    assert "<th>ช่วงวันที่</th>" in template
    assert "<th>สถานะ</th>" in template
    for hook in (
        "delegation-list-wrap",
        "delegation-row",
        "delegation-delegate",
        "delegation-date",
        "delegation-status-cell",
        "delegation-action-cell",
        "delegation-cancel-form",
        "delegation-cancel-button",
        "delegation-row-ended",
        "delegation-empty-row",
    ):
        assert hook in template
    assert "{% if item.end_date >= today %}" in template
    assert "{% if item.end_date < today %}" in template
    assert "{% url 'approvals:delegation_delete' item.id %}" in template
    assert "ยืนยันยกเลิกการมอบหมายนี้ใช่หรือไม่" in template
    assert ">ยกเลิก<" in template


def test_delegation_page_primary_and_non_primary_permissions(client, delegation_page_setup):
    setup = delegation_page_setup

    # Outsider denied
    client.force_login(setup["outsider"])
    assert client.get(reverse("approvals:delegation")).status_code == 403

    # Backup (non-primary) approver denied
    client.force_login(setup["backup"])
    assert client.get(reverse("approvals:delegation")).status_code == 403

    # Primary approver allowed
    client.force_login(setup["primary"])
    response = client.get(reverse("approvals:delegation"))
    assert response.status_code == 200


def test_active_and_future_delegation_render_post_cancel_form(client, delegation_page_setup):
    setup = delegation_page_setup
    today = timezone.localdate()

    # Active delegation (includes today)
    active = ApproverDelegation.objects.create(
        delegator=setup["primary"],
        delegate=setup["delegate"],
        start_date=today,
        end_date=today + timedelta(days=2),
    )

    client.force_login(setup["primary"])
    response = client.get(reverse("approvals:delegation"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "status-active" in html
    assert "กำลังใช้" in html
    assert "delegation-row-active" in html

    action_url = reverse("approvals:delegation_delete", args=[active.id])
    assert action_url in html

    form_match = re.search(
        rf'<form class="delegation-cancel-form" method="post" action="{re.escape(action_url)}"[^>]*>(.*?)</form>',
        html,
        re.DOTALL,
    )
    assert form_match is not None
    form_content = form_match.group(1)
    assert 'name="csrfmiddlewaretoken"' in form_content
    assert "ยืนยันยกเลิกการมอบหมายนี้ใช่หรือไม่" in form_match.group(0)
    assert '<button class="outline danger delegation-cancel-button" type="submit">ยกเลิก</button>' in form_content

    # Delete endpoint is POST-only
    assert client.get(action_url).status_code == 405


def test_future_delegation_renders_pending_status_and_cancel_form(client, delegation_page_setup):
    setup = delegation_page_setup
    today = timezone.localdate()

    future = ApproverDelegation.objects.create(
        delegator=setup["primary"],
        delegate=setup["delegate"],
        start_date=today + timedelta(days=3),
        end_date=today + timedelta(days=5),
    )

    client.force_login(setup["primary"])
    response = client.get(reverse("approvals:delegation"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "status-pending" in html
    assert "รอถึงวัน" in html
    action_url = reverse("approvals:delegation_delete", args=[future.id])
    assert action_url in html
    assert '<button class="outline danger delegation-cancel-button" type="submit">ยกเลิก</button>' in html


def test_ended_delegation_is_distinct_and_has_no_cancel(client, delegation_page_setup):
    setup = delegation_page_setup
    today = timezone.localdate()

    ended = ApproverDelegation.objects.create(
        delegator=setup["primary"],
        delegate=setup["delegate"],
        start_date=today - timedelta(days=5),
        end_date=today - timedelta(days=1),
    )

    client.force_login(setup["primary"])
    response = client.get(reverse("approvals:delegation"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "delegation-row-ended" in html
    assert "status-draft" in html
    assert "สิ้นสุด" in html
    action_url = reverse("approvals:delegation_delete", args=[ended.id])
    assert action_url not in html
    assert "delegation-cancel-form" not in html


def test_owner_scoped_delete_preserves_post_semantics(client, delegation_page_setup):
    setup = delegation_page_setup
    today = timezone.localdate()

    other_delegation = ApproverDelegation.objects.create(
        delegator=setup["other_primary"],
        delegate=setup["delegate"],
        start_date=today,
        end_date=today + timedelta(days=2),
    )

    # Primary cannot delete other user's delegation
    client.force_login(setup["primary"])
    delete_url = reverse("approvals:delegation_delete", args=[other_delegation.id])
    assert client.post(delete_url).status_code == 404

    # Primary can delete own delegation
    own_delegation = ApproverDelegation.objects.create(
        delegator=setup["primary"],
        delegate=setup["delegate"],
        start_date=today,
        end_date=today + timedelta(days=2),
    )
    own_url = reverse("approvals:delegation_delete", args=[own_delegation.id])
    response = client.post(own_url)
    assert response.status_code == 302
    assert response.url == reverse("approvals:delegation")
    assert not ApproverDelegation.objects.filter(pk=own_delegation.pk).exists()

    # Attempt to delete already-ended delegation via POST fails with error message
    ended_delegation = ApproverDelegation.objects.create(
        delegator=setup["primary"],
        delegate=setup["delegate"],
        start_date=today - timedelta(days=4),
        end_date=today - timedelta(days=1),
    )
    ended_url = reverse("approvals:delegation_delete", args=[ended_delegation.id])
    response = client.post(ended_url, follow=True)
    assert response.status_code == 200
    assert ApproverDelegation.objects.filter(pk=ended_delegation.pk).exists()
    assert "รายการนี้สิ้นสุดแล้วและยกเลิกไม่ได้" in response.content.decode()


def test_ux8_css_is_delegation_scoped_and_exact_768_stays_desktop():
    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    marker = "/* UX-8 Approver Delegation Mobile Clarity */"

    assert marker in css
    ux8 = css.split(marker, 1)[1]
    assert "@media (max-width: 47.99rem)" in ux8
    assert "@media (max-width: 48rem)" not in ux8
    assert ".delegation-list-wrap .delegation-table" in ux8
    assert "grid-template-areas" in ux8
    assert 'content: "ผู้รักษาการ"' in ux8
    assert 'content: "ช่วงวันที่"' in ux8
    assert "overflow-wrap: anywhere" in ux8
    assert "min-height: 44px" in ux8
    assert ".delegation-table .delegation-row-ended" in ux8
    assert "border-style: dashed" in ux8
    ended_action_rule = re.search(
        r"\.delegation-table \.delegation-row-ended > \.delegation-action-cell\s*\{(?P<body>[^}]*)\}",
        ux8,
    )
    assert ended_action_rule is not None
    assert "display: none;" in ended_action_rule.group("body")
    assert ":has(" not in ux8

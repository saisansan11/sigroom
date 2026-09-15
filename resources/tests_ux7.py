"""UX-7 contracts for outage management on narrow screens."""
from datetime import timedelta
from pathlib import Path
import re

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from resources.models import Resource, ResourceOutage


pytestmark = pytest.mark.django_db


@pytest.fixture
def outage_page_setup():
    unit = Unit.objects.create(code="OPS", name="งานอาคารสถานที่")
    custodian = User.objects.create_user(
        username="ux7-custodian",
        email="ux7-custodian@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    outsider = User.objects.create_user(
        username="ux7-outsider",
        email="ux7-outsider@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    room = Resource.objects.create(code="UX7-ROOM", name="ห้องทดสอบ UX-7")
    room.custodians.add(custodian)
    return custodian, outsider, room


def _outage(room, custodian, *, ended=False):
    start_at = timezone.now() + timedelta(days=1)
    return ResourceOutage.objects.create(
        resource=room,
        start_at=start_at,
        end_at=start_at + timedelta(hours=2),
        reason="ซ่อมระบบปรับอากาศและอุปกรณ์ควบคุมภายในห้องเป็นข้อความภาษาไทยที่ยาวต่อเนื่อง",
        created_by=custodian,
        ended_early_at=timezone.now() if ended else None,
    )


def test_outage_template_keeps_one_semantic_table_and_responsive_hooks():
    template = (Path(settings.BASE_DIR) / "templates" / "resources" / "outage.html").read_text(encoding="utf-8")

    assert template.count('<table class="outage-table">') == 1
    for hook in (
        "outage-list-wrap",
        "outage-row",
        "outage-time",
        "outage-reason",
        "outage-status-cell",
        "outage-action-cell",
        "outage-row-ended",
    ):
        assert hook in template
    assert "{% if item.ended_early_at %}" in template
    assert "{% if not item.ended_early_at %}" in template


def test_outage_page_preserves_permission_and_active_post_action(client, outage_page_setup):
    custodian, outsider, room = outage_page_setup
    outage = _outage(room, custodian)

    client.force_login(outsider)
    assert client.get(reverse("resources:outage", args=[room.code])).status_code == 403

    client.force_login(custodian)
    response = client.get(reverse("resources:outage", args=[room.code]))
    html = response.content.decode()
    action_url = reverse("resources:outage_end", args=[outage.id])

    assert response.status_code == 200
    action_form = re.search(
        rf'<form class="outage-end-form" method="post" action="{re.escape(action_url)}">(.*?)</form>',
        html,
        re.DOTALL,
    )
    assert action_form is not None
    assert 'name="csrfmiddlewaretoken"' in action_form.group(1)
    assert '<button class="outline danger outage-end-button" type="submit">สิ้นสุดก่อนกำหนด</button>' in action_form.group(1)
    assert client.get(action_url).status_code == 405


def test_ended_early_outage_is_distinct_and_has_no_action(client, outage_page_setup):
    custodian, _, room = outage_page_setup
    outage = _outage(room, custodian, ended=True)
    client.force_login(custodian)

    html = client.get(reverse("resources:outage", args=[room.code])).content.decode()

    assert 'class="outage-row outage-row-ended"' in html
    assert '<span class="status status-ended_early">สิ้นสุดก่อนกำหนด</span>' in html
    assert reverse("resources:outage_end", args=[outage.id]) not in html
    assert "outage-end-form" not in html


def test_ux7_css_is_outage_scoped_and_exact_768_stays_desktop():
    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    marker = "/* UX-7 Outage Management Mobile Clarity */"

    assert marker in css
    ux7 = css.split(marker, 1)[1]
    assert "@media (max-width: 47.99rem)" in ux7
    assert "@media (max-width: 48rem)" not in ux7
    assert ".outage-list-wrap .outage-table" in ux7
    assert "grid-template-areas" in ux7
    assert 'content: "ช่วงเวลา"' in ux7
    assert 'content: "เหตุผล"' in ux7
    assert "overflow-wrap: anywhere" in ux7
    assert "min-height: 44px" in ux7
    assert ".outage-table .outage-row-ended" in ux7
    assert "border-style: dashed" in ux7
    ended_action_rule = re.search(
        r"\.outage-table \.outage-row-ended > \.outage-action-cell\s*\{(?P<body>[^}]*)\}",
        ux7,
    )
    assert ended_action_rule is not None
    assert "display: none;" in ended_action_rule.group("body")
    assert ":has(" not in ux7

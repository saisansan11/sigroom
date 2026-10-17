"""UX-10 contracts for usage-status mobile clarity."""
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def usage_mobile_setup():
    unit = Unit.objects.create(code="U-UX10", name="หน่วยทดสอบ UX-10")
    requester = User.objects.create_user(
        username="ux10-requester",
        email="ux10-requester@signalschool.ac.th",
        password="Test-Password-123",
        unit=unit,
    )
    custodian = User.objects.create_user(
        username="ux10-custodian",
        email="ux10-custodian@signalschool.ac.th",
        password="Test-Password-123",
        unit=unit,
    )
    outsider = User.objects.create_user(
        username="ux10-outsider",
        email="ux10-outsider@signalschool.ac.th",
        password="Test-Password-123",
        unit=unit,
    )
    room = Resource.objects.create(code="UX10-ROOM", name="ห้องทดสอบสถานะการใช้งาน UX-10", owner_unit=unit)
    ResourceRule.objects.create(resource=room)
    room.custodians.add(custodian)

    now = timezone.now()
    open_end = now - timedelta(hours=1)
    open_booking = Booking.objects.create(
        room=room,
        requester=requester,
        unit=unit,
        responsible_name="ผู้รับผิดชอบ UX-10",
        responsible_phone="0810000000",
        title="กิจกรรมที่แก้สถานะได้",
        start_at=open_end - timedelta(hours=2),
        end_at=open_end,
        request_status=Booking.RequestStatus.APPROVED,
        usage_status=Booking.UsageStatus.USED,
    )

    closed_end = now - timedelta(hours=2)
    closed_booking = Booking.objects.create(
        room=room,
        requester=requester,
        unit=unit,
        responsible_name="ผู้รับผิดชอบ UX-10",
        responsible_phone="0810000000",
        title="กิจกรรมที่ปิดการแก้สถานะ",
        start_at=closed_end - timedelta(hours=2),
        end_at=closed_end,
        request_status=Booking.RequestStatus.APPROVED,
        usage_status=Booking.UsageStatus.ROOM_UNAVAILABLE,
    )
    return {
        "unit": unit,
        "requester": requester,
        "custodian": custodian,
        "outsider": outsider,
        "room": room,
        "open_booking": open_booking,
        "closed_booking": closed_booking,
    }


def test_usage_template_preserves_one_table_and_update_contracts():
    template = (Path(settings.BASE_DIR) / "templates" / "usage" / "list.html").read_text(encoding="utf-8")

    assert template.count("<table") == 1
    for hook in (
        "usage-list-wrap",
        "usage-table",
        "usage-row",
        "usage-time",
        "usage-room",
        "usage-requester",
        "usage-status-cell",
        "usage-action-cell",
        "usage-status-form",
        "usage-status-button",
        "usage-row-closed",
        "usage-closed-note",
    ):
        assert hook in template

    assert "{% url 'usage:update' booking.pk %}" in template
    assert 'method="post"' in template
    assert "{% csrf_token %}" in template
    assert 'name="status" value="used"' in template
    assert 'name="status" value="no_show"' in template
    assert "booking.usage_change_open" in template
    assert "booking.usage_status == 'used'" in template
    assert "booking.usage_status == 'no_show'" in template
    assert "ใช้งานแล้ว" in template
    assert "ไม่มาใช้" in template
    assert "พ้นกำหนดแก้ไข" in template


def test_usage_list_keeps_permission_and_open_closed_rendering(client, usage_mobile_setup):
    setup = usage_mobile_setup

    client.force_login(setup["outsider"])
    assert client.get(reverse("usage:list")).status_code == 403

    client.force_login(setup["custodian"])
    response = client.get(reverse("usage:list"))
    html = response.content.decode()

    assert response.status_code == 200
    assert html.count("<table") == 1
    assert "usage-row-editable" in html
    assert "usage-row-closed" in html
    assert reverse("usage:update", args=[setup["open_booking"].pk]) in html
    assert reverse("usage:update", args=[setup["closed_booking"].pk]) not in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert 'name="status" value="used" disabled' in html
    assert 'name="status" value="no_show"' in html
    assert "พ้นกำหนดแก้ไข" in html


def test_usage_update_remains_post_only(client, usage_mobile_setup):
    setup = usage_mobile_setup
    client.force_login(setup["custodian"])
    response = client.get(reverse("usage:update", args=[setup["open_booking"].pk]))
    assert response.status_code == 405


def test_ux10_css_is_usage_scoped_and_mobile_only():
    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    marker = "/* UX-10 Usage Status Mobile Clarity */"

    assert marker in css
    ux10 = css.split(marker, 1)[1]
    assert "@media (max-width: 47.99rem)" in ux10
    assert "@media (max-width: 48rem)" not in ux10
    assert ".usage-list-wrap .usage-table" in ux10
    assert ".usage-table .usage-row" in ux10
    assert ".usage-status-form" in ux10
    assert ".usage-status-button" in ux10
    assert ".usage-row-closed" in ux10
    assert "min-width: 0" in ux10
    assert "min-height: 44px" in ux10
    assert "overflow-wrap: anywhere" in ux10
    assert ":has(" not in ux10


def test_usage_service_scope_separates_online_from_learning(client, usage_mobile_setup):
    setup = usage_mobile_setup
    online_room = Resource.objects.create(
        code="UX10-ONLINE",
        name="ห้องสอนออนไลน์ UX-10",
        owner_unit=setup["unit"],
        room_category=Resource.Category.ONLINE,
    )
    ResourceRule.objects.create(resource=online_room)
    online_room.custodians.add(setup["custodian"])
    now = timezone.now()
    online_booking = Booking.objects.create(
        room=online_room,
        requester=setup["requester"],
        unit=setup["unit"],
        responsible_name="ผู้รับผิดชอบออนไลน์",
        responsible_phone="0810000001",
        title="สอนออนไลน์",
        start_at=now - timedelta(hours=3),
        end_at=now - timedelta(hours=2),
        request_status=Booking.RequestStatus.APPROVED,
        usage_status=Booking.UsageStatus.USED,
    )
    client.force_login(setup["custodian"])

    online = client.get(f"{reverse('usage:list')}?service=online")
    online_html = online.content.decode("utf-8")
    assert online.status_code == 200
    assert online_room.code in online_html
    assert setup["room"].code not in online_html
    assert "เฉพาะห้องสอนออนไลน์ที่ท่านได้รับมอบหมาย" in online_html

    learning = client.get(f"{reverse('usage:list')}?service=learning")
    learning_html = learning.content.decode("utf-8")
    assert learning.status_code == 200
    assert setup["room"].code in learning_html
    assert online_room.code not in learning_html

    # Even when the same custodian owns both services, a scoped POST cannot cross sections.
    cross = client.post(
        f"{reverse('usage:update', args=[setup['open_booking'].pk])}?service=online",
        {"status": Booking.UsageStatus.NO_SHOW},
    )
    assert cross.status_code == 403
    setup["open_booking"].refresh_from_db()
    assert setup["open_booking"].usage_status == Booking.UsageStatus.USED
    online_booking.refresh_from_db()
    assert online_booking.usage_status == Booking.UsageStatus.USED

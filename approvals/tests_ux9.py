"""UX-9 contracts for approver queue decision clarity."""
from datetime import datetime, time, timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking, BookingSeries
from bookings.series_services import create_series
from resources.models import Resource, ResourceApprover, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def approval_queue_setup():
    unit = Unit.objects.create(code="HQ-UX9", name="กองบังคับการ UX-9")
    requester = User.objects.create_user(
        username="ux9-requester",
        email="ux9-requester@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    primary = User.objects.create_user(
        username="ux9-primary",
        email="ux9-primary@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    backup = User.objects.create_user(
        username="ux9-backup",
        email="ux9-backup@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    outsider = User.objects.create_user(
        username="ux9-outsider",
        email="ux9-outsider@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
    )
    room = Resource.objects.create(code="UX9-ROOM", name="ห้องทดสอบ UX-9")
    ResourceRule.objects.create(
        resource=room,
        approval_policy=ResourceRule.ApprovalPolicy.REQUIRED,
        service_start=time(7),
        service_end=time(21),
    )
    ResourceApprover.objects.create(resource=room, user=primary, is_primary=True)
    ResourceApprover.objects.create(resource=room, user=backup, is_primary=False)
    return {
        "unit": unit,
        "requester": requester,
        "primary": primary,
        "backup": backup,
        "outsider": outsider,
        "room": room,
    }


def _make_series(setup):
    start_date = timezone.localdate() + timedelta(days=7)
    zone = timezone.get_current_timezone()
    start_at = timezone.make_aware(datetime.combine(start_date, time(9)), zone)
    end_at = timezone.make_aware(datetime.combine(start_date, time(10)), zone)
    template = Booking(
        room=setup["room"],
        requester=setup["requester"],
        unit=setup["unit"],
        responsible_name="ร.อ.สมชาย",
        responsible_phone="0810000000",
        title="ชุดประชุม UX-9",
        start_at=start_at,
        end_at=end_at,
    )
    template._series_equipment = []
    params = {
        "freq": BookingSeries.Frequency.WEEKLY,
        "weekdays": [start_date.weekday()],
        "custom_dates": [],
        "start_date": start_date,
        "end_date": None,
        "requested_count": 3,
        "time_start": time(9),
        "time_end": time(10),
    }
    return create_series(setup["room"], params, template, setup["requester"], now=timezone.now())


def test_queue_template_preserves_decision_contracts_and_hooks():
    template = (Path(settings.BASE_DIR) / "templates" / "approvals" / "queue.html").read_text(encoding="utf-8")

    for hook in (
        "approval-queue-list",
        "approval-queue-card",
        "approval-queue-actions",
        "approval-queue-card-series",
        "series-decision-panel",
        "series-occurrence-details",
        "series-reason-grid",
        "series-decision-actions",
    ):
        assert hook in template

    for url_name in (
        "approvals:approve",
        "approvals:reject",
        "approvals:amendment_approve",
        "approvals:amendment_reject",
        "approvals:series_decide",
    ):
        assert url_name in template

    assert template.count('method="post"') >= 5
    assert template.count("{% csrf_token %}") >= 5
    assert 'name="excluded" value="{{ item.id }}"' in template
    assert 'name="reason_excluded" maxlength="500"' in template
    assert 'name="reason_reject" maxlength="500"' in template
    assert 'name="action" value="approve"' in template
    assert 'name="action" value="reject"' in template
    assert 'name="reason" required maxlength="500" list="rejection-reasons"' in template


def test_queue_permission_contract_is_unchanged(client, approval_queue_setup):
    setup = approval_queue_setup

    client.force_login(setup["outsider"])
    assert client.get(reverse("approvals:queue")).status_code == 403

    client.force_login(setup["primary"])
    assert client.get(reverse("approvals:queue")).status_code == 200

    client.force_login(setup["backup"])
    assert client.get(reverse("approvals:queue")).status_code == 200


def test_series_queue_card_keeps_occurrence_ids_and_post_fields(client, approval_queue_setup):
    setup = approval_queue_setup
    series = _make_series(setup)
    occurrence_ids = list(series.occurrences.order_by("start_at").values_list("id", flat=True))

    client.force_login(setup["primary"])
    response = client.get(reverse("approvals:queue"))
    html = response.content.decode()

    assert response.status_code == 200
    assert "approval-queue-card-series" in html
    assert "series-decision-panel" in html
    assert "series-occurrence-details" in html
    assert "series-reason-grid" in html
    assert "series-decision-actions" in html
    assert reverse("approvals:series_decide", args=[series.id]) in html
    assert 'method="post"' in html
    assert 'name="csrfmiddlewaretoken"' in html
    assert 'name="excluded"' in html
    assert 'name="reason_excluded"' in html
    assert 'name="reason_reject"' in html
    assert 'name="action" value="approve"' in html
    assert 'name="action" value="reject"' in html
    for occurrence_id in occurrence_ids:
        assert f'value="{occurrence_id}"' in html


def test_ux9_css_is_queue_scoped_and_mobile_only():
    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    marker = "/* UX-9 Approver Queue Decision Clarity */"

    assert marker in css
    ux9 = css.split(marker, 1)[1]
    assert "@media (max-width: 47.99rem)" in ux9
    assert "@media (max-width: 48rem)" not in ux9
    assert ".approval-queue-card" in ux9
    assert ".approval-queue-actions" in ux9
    assert ".series-decision-panel" in ux9
    assert ".series-reason-grid" in ux9
    assert ".series-decision-actions" in ux9
    assert "min-height: 44px" in ux9
    assert "overflow-wrap: anywhere" in ux9
    assert ":has(" not in ux9

"""UX-5 contracts for requester-facing series booking management."""
from datetime import timedelta
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking, BookingSeries, SeriesSkip
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def ux5_setup():
    unit = Unit.objects.create(code="UX5", name="หน่วยทดสอบ UX-5")
    owner = User.objects.create_user(
        username="ux5_owner",
        email="ux5_owner@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        phone="0811112222",
    )
    viewer = User.objects.create_user(
        username="ux5_viewer",
        email="ux5_viewer@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        phone="0822223333",
    )
    room = Resource.objects.create(
        code="UX5-101",
        name="ห้องทดสอบชุดการจอง",
        building="อาคาร UX-5",
        capacity=30,
    )
    ResourceRule.objects.create(
        resource=room,
        approval_policy=ResourceRule.ApprovalPolicy.AUTO,
    )

    now = timezone.now()
    series = BookingSeries.objects.create(
        room=room,
        created_by=owner,
        unit=unit,
        freq=BookingSeries.Frequency.WEEKLY,
        weekdays=[timezone.localdate().weekday()],
        start_date=timezone.localdate() - timedelta(days=2),
        end_date=timezone.localdate() + timedelta(days=14),
        time_start=now.time().replace(second=0, microsecond=0),
        time_end=(now + timedelta(hours=1)).time().replace(second=0, microsecond=0),
    )

    common = {
        "room": room,
        "requester": owner,
        "unit": unit,
        "responsible_name": "ผู้ทดสอบ UX-5",
        "responsible_phone": "0811112222",
        "title": "ชุดทดสอบ UX-5",
        "attendees": 10,
        "series": series,
    }
    past_approved = Booking.objects.create(
        **common,
        series_index=1,
        start_at=now - timedelta(days=2),
        end_at=now - timedelta(days=2) + timedelta(hours=1),
        request_status=Booking.RequestStatus.APPROVED,
    )
    future_pending = Booking.objects.create(
        **common,
        series_index=2,
        start_at=now + timedelta(days=2),
        end_at=now + timedelta(days=2, hours=1),
        request_status=Booking.RequestStatus.PENDING,
    )
    future_approved = Booking.objects.create(
        **common,
        series_index=3,
        start_at=now + timedelta(days=4),
        end_at=now + timedelta(days=4, hours=1),
        request_status=Booking.RequestStatus.APPROVED,
        decision_reason="อนุมัติแล้ว",
    )
    future_cancelled = Booking.objects.create(
        **common,
        series_index=4,
        start_at=now + timedelta(days=6),
        end_at=now + timedelta(days=6, hours=1),
        request_status=Booking.RequestStatus.CANCELLED,
    )
    skip = SeriesSkip.objects.create(
        series=series,
        occur_date=timezone.localdate() + timedelta(days=8),
        kind=SeriesSkip.Kind.CONFLICT,
        reason="ช่วงเวลานี้มีรายการจองอื่น",
    )
    return {
        "unit": unit,
        "owner": owner,
        "viewer": viewer,
        "room": room,
        "series": series,
        "past_approved": past_approved,
        "future_pending": future_pending,
        "future_approved": future_approved,
        "future_cancelled": future_cancelled,
        "skip": skip,
    }


def test_owner_keeps_existing_series_actions_and_exact_confirm_copy(client, ux5_setup):
    data = ux5_setup
    client.force_login(data["owner"])

    response = client.get(reverse("bookings:series_detail", args=[data["series"].pk]))
    html = response.content.decode()

    assert response.status_code == 200
    assert reverse("bookings:booking_cancel", args=[data["future_pending"].pk]) in html
    assert reverse("bookings:booking_cancel", args=[data["future_approved"].pk]) in html
    assert reverse("bookings:booking_cancel", args=[data["past_approved"].pk]) not in html
    assert reverse("bookings:booking_cancel", args=[data["future_cancelled"].pk]) not in html
    assert reverse("bookings:series_cancel_remaining", args=[data["series"].pk]) in html
    assert "ยืนยันยกเลิกการจองครั้งนี้ใช่หรือไม่" in html
    assert "ยืนยันยกเลิกครั้งที่เหลือทั้งหมดใช่หรือไม่" in html


def test_same_unit_viewer_can_view_but_gains_no_cancel_actions(client, ux5_setup):
    data = ux5_setup
    client.force_login(data["viewer"])

    response = client.get(reverse("bookings:series_detail", args=[data["series"].pk]))
    html = response.content.decode()

    assert response.status_code == 200
    assert "series-occurrences-table" in html
    assert reverse("bookings:booking_detail", args=[data["future_pending"].pk]) in html
    for booking in (
        data["past_approved"],
        data["future_pending"],
        data["future_approved"],
        data["future_cancelled"],
    ):
        assert reverse("bookings:booking_cancel", args=[booking.pk]) not in html
    assert reverse("bookings:series_cancel_remaining", args=[data["series"].pk]) not in html


def test_series_detail_keeps_single_table_responsive_hooks_and_skip_reason(client, ux5_setup):
    data = ux5_setup
    client.force_login(data["owner"])

    html = client.get(reverse("bookings:series_detail", args=[data["series"].pk])).content.decode()

    assert html.count('<table class="series-occurrences-table">') == 1
    for hook in (
        "series-occurrences-wrap",
        "series-occurrence-row",
        "series-occurrence-index",
        "series-occurrence-datetime",
        "series-occurrence-status",
        "series-occurrence-note",
        "series-occurrence-actions",
        "series-skip-row",
    ):
        assert hook in html
    assert "ช่วงเวลานี้มีรายการจองอื่น" in html
    assert "ข้าม" in html


def test_ux5_template_preserves_cancellation_condition_and_endpoints():
    template = (Path(settings.BASE_DIR) / "templates" / "bookings" / "series_detail.html").read_text(encoding="utf-8")

    assert (
        "{% if can_cancel and booking.start_at > now and booking.request_status == 'pending' or can_cancel and "
        "booking.start_at > now and booking.request_status == 'approved' %}"
    ) in template
    assert "{% url 'bookings:booking_cancel' booking.id %}" in template
    assert "{% url 'bookings:series_cancel_remaining' series.id %}" in template


def test_ux5_css_contract_is_series_scoped_and_excludes_exact_768px():
    css = (Path(settings.BASE_DIR) / "static" / "css" / "app.css").read_text(encoding="utf-8")
    marker = "/* UX-5 Series Booking Management */"

    assert marker in css
    ux5 = css.split(marker, 1)[1]
    assert "@media (max-width: 47.99rem)" in ux5
    assert ".series-occurrences-wrap .series-occurrences-table" in ux5
    assert "min-width: 0" in ux5
    assert ".series-occurrence-actions" in ux5
    assert "min-height: 44px" in ux5
    assert ".series-skip-row" in ux5
    assert ".series-flags-grid" in ux5
    assert ":has(" not in css

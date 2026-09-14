"""UX-3 My Bookings and Request Tracking test suite."""
from datetime import time, timedelta
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking, BookingSeries
from resources.models import Resource, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def ux3_setup():
    unit = Unit.objects.create(code="UX3", name="หน่วยทดสอบ UX-3")
    user = User.objects.create_user(
        username="ux3_user",
        email="ux3_user@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.อ.",
        first_name="สมหวัง",
        last_name="จองดี",
        phone="081-111-2222",
    )
    room = Resource.objects.create(
        code="UX3-101",
        name="ห้องบรรยาย 101",
        building="อาคารทดสอบ",
        floor="1",
        capacity=30,
    )
    ResourceRule.objects.create(
        resource=room,
        approval_policy=ResourceRule.ApprovalPolicy.AUTO,
        service_start=time(7, 0),
        service_end=time(21, 0),
        allow_series=True,
        max_series_occurrences=10,
    )
    return {"unit": unit, "user": user, "room": room}


def test_my_bookings_model_fields_and_tabs(client, ux3_setup):
    """Test BookingSeries creation with real model fields only and verify tab filtering."""
    data = ux3_setup
    user = data["user"]
    unit = data["unit"]
    room = data["room"]
    now = timezone.now()

    # Real BookingSeries fields only: freq, weekdays, custom_dates, start_date, end_date, requested_count, time_start, time_end
    series = BookingSeries.objects.create(
        room=room,
        created_by=user,
        unit=unit,
        freq=BookingSeries.Frequency.WEEKLY,
        weekdays=[0, 2],
        custom_dates=[],
        start_date=timezone.localdate(),
        end_date=None,
        requested_count=4,
        time_start=time(9, 0),
        time_end=time(10, 0),
    )

    # Series occurrence
    Booking.objects.create(
        room=room,
        requester=user,
        unit=unit,
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="การจองแบบชุด ครั้งที่ 1",
        start_at=now + timedelta(days=2, hours=1),
        end_at=now + timedelta(days=2, hours=2),
        request_status=Booking.RequestStatus.APPROVED,
        series=series,
        series_index=1,
    )

    # Standalone upcoming approved booking
    approved_bk = Booking.objects.create(
        room=room,
        requester=user,
        unit=unit,
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="กิจกรรมอนุมัติแล้ว",
        start_at=now + timedelta(days=1, hours=1),
        end_at=now + timedelta(days=1, hours=2),
        request_status=Booking.RequestStatus.APPROVED,
    )

    # Standalone upcoming pending booking
    pending_bk = Booking.objects.create(
        room=room,
        requester=user,
        unit=unit,
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="กิจกรรมรออนุมัติ",
        start_at=now + timedelta(days=1, hours=3),
        end_at=now + timedelta(days=1, hours=4),
        request_status=Booking.RequestStatus.PENDING,
    )

    # Draft booking
    draft_bk = Booking.objects.create(
        room=room,
        requester=user,
        unit=unit,
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="กิจกรรมฉบับร่าง",
        start_at=now + timedelta(days=3, hours=1),
        end_at=now + timedelta(days=3, hours=2),
        request_status=Booking.RequestStatus.DRAFT,
    )

    # Closed (rejected) booking
    rejected_bk = Booking.objects.create(
        room=room,
        requester=user,
        unit=unit,
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="กิจกรรมถูกปฏิเสธ",
        start_at=now - timedelta(days=1, hours=2),
        end_at=now - timedelta(days=1, hours=1),
        request_status=Booking.RequestStatus.REJECTED,
        decision_reason="ห้องไม่พร้อมใช้งาน",
    )

    client.force_login(user)

    # 1. Upcoming tab
    resp_upcoming = client.get(reverse("bookings:my_bookings"))
    content_upcoming = resp_upcoming.content.decode()
    assert resp_upcoming.status_code == 200
    assert "my-bookings-tabs" in content_upcoming
    assert "my-bookings-table-wrap" in content_upcoming
    assert "my-series-table-wrap" in content_upcoming
    assert "my-bookings-table" in content_upcoming
    assert "my-series-table" in content_upcoming
    assert "กิจกรรมอนุมัติแล้ว" in content_upcoming
    assert "กิจกรรมรออนุมัติ" in content_upcoming
    # Series item display
    assert series.room.code in content_upcoming
    assert "ดูทั้งชุด" in content_upcoming

    # Detail link on all rows
    assert reverse("bookings:booking_detail", args=[approved_bk.id]) in content_upcoming
    assert reverse("bookings:booking_detail", args=[pending_bk.id]) in content_upcoming

    # Rebook link only for approved
    assert f"rebook={approved_bk.id}" in content_upcoming
    assert f"rebook={pending_bk.id}" not in content_upcoming

    # Single canonical table for bookings
    assert content_upcoming.count('<table class="my-bookings-table">') == 1

    # 2. Drafts tab
    resp_drafts = client.get(reverse("bookings:my_bookings"), {"tab": "drafts"})
    content_drafts = resp_drafts.content.decode()
    assert resp_drafts.status_code == 200
    assert "กิจกรรมฉบับร่าง" in content_drafts
    assert reverse("bookings:booking_detail", args=[draft_bk.id]) in content_drafts
    assert f"rebook={draft_bk.id}" not in content_drafts

    # 3. Closed tab
    resp_closed = client.get(reverse("bookings:my_bookings"), {"tab": "closed"})
    content_closed = resp_closed.content.decode()
    assert resp_closed.status_code == 200
    assert "กิจกรรมถูกปฏิเสธ" in content_closed
    assert "ห้องไม่พร้อมใช้งาน" in content_closed
    assert reverse("bookings:booking_detail", args=[rejected_bk.id]) in content_closed
    assert f"rebook={rejected_bk.id}" not in content_closed


def test_my_bookings_empty_state_and_markup_contracts(client, ux3_setup):
    """Test empty state preservation and semantic markup classes."""
    data = ux3_setup
    user = data["user"]
    client.force_login(user)

    resp = client.get(reverse("bookings:my_bookings"))
    content = resp.content.decode()
    assert resp.status_code == 200
    assert "ยังไม่มีรายการในหมวดนี้" in content
    assert "empty-state" in content
    assert "empty-row" in content
    assert "my-bookings-table" in content


def test_my_bookings_css_contracts():
    """Verify CSS architecture: scoped selectors, exclusion of 768px, no :has(), and clean formatting."""
    css_path = Path(__file__).resolve().parent.parent / "static" / "css" / "app.css"
    content = css_path.read_text(encoding="utf-8")

    # Mobile breakpoint must exclude exact 768px (using max-width: 47.99rem or 767.98px)
    assert "@media (max-width: 47.99rem)" in content

    # Scoped selectors with higher specificity than .table-wrap table { min-width: 42rem; }
    assert ".my-bookings-table-wrap .my-bookings-table" in content
    assert ".my-series-table-wrap .my-series-table" in content

    # Mobile card hierarchy order properties
    assert ".booking-cell-title" in content
    assert ".booking-cell-status" in content
    assert ".booking-cell-datetime" in content
    assert ".booking-cell-room" in content
    assert ".booking-cell-equipment" in content
    assert ".booking-cell-actions" in content

    # Touch target minimum height >= 44px
    assert "min-height: 44px;" in content

    # Tabs wrap on mobile
    assert ".my-bookings-tabs" in content
    assert "flex-wrap: wrap;" in content

    # No :has() in CSS
    assert ":has(" not in content

    # Exactly one newline at EOF (no trailing blank lines)
    assert content.endswith("\n")
    assert not content.endswith("\n\n")

    # No trailing whitespace on any line
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        assert line == line.rstrip(), f"Line {idx} has trailing whitespace"

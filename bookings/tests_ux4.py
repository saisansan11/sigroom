"""UX-4 Booking Detail, Action Center, DOM order and Presentation tests."""
from datetime import time, timedelta
import re

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from approvals.models import Approval
from bookings.models import Booking
from resources.models import Resource, ResourceApprover, ResourceRule

pytestmark = pytest.mark.django_db


@pytest.fixture
def ux4_setup():
    unit = Unit.objects.create(code="UX4", name="หน่วยทดสอบ UX-4")
    requester = User.objects.create_user(
        username="ux4_requester",
        email="ux4_req@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.อ.",
        first_name="สมหวัง",
        last_name="ผู้ขอ",
        phone="081-111-2222",
    )
    approver = User.objects.create_user(
        username="ux4_approver",
        email="ux4_app@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="พ.ท.",
        first_name="อนุมัติ",
        last_name="อำนาจ",
        phone="082-222-3333",
    )
    viewer = User.objects.create_user(
        username="ux4_viewer",
        email="ux4_view@signalschool.ac.th",
        password="Password-2569",
        unit=unit,
        rank="ร.ท.",
        first_name="สังเกต",
        last_name="ร่วมหน่วย",
        phone="083-333-4444",
    )
    room_req = Resource.objects.create(
        code="UX4-REQ",
        name="ห้องประชุมอนุมัติ",
        room_category=Resource.Category.MEETING,
    )
    ResourceRule.objects.create(
        resource=room_req,
        approval_policy=ResourceRule.ApprovalPolicy.REQUIRED,
        service_start=time(7, 0),
        service_end=time(21, 0),
        cancel_cutoff_hours=4,
    )
    ResourceApprover.objects.create(resource=room_req, user=approver, is_primary=True)

    room_auto = Resource.objects.create(
        code="UX4-AUTO",
        name="ห้องบรรยายอัตโนมัติ",
        room_category=Resource.Category.CLASSROOM,
    )
    ResourceRule.objects.create(
        resource=room_auto,
        approval_policy=ResourceRule.ApprovalPolicy.AUTO,
        service_start=time(7, 0),
        service_end=time(21, 0),
        cancel_cutoff_hours=4,
    )

    return {
        "unit": unit,
        "requester": requester,
        "approver": approver,
        "viewer": viewer,
        "room_req": room_req,
        "room_auto": room_auto,
    }


def test_ux4_dom_order_with_deadline_and_action_center(client, ux4_setup):
    """Assert DOM order hero -> optional deadline -> action center -> booking-detail-card -> history."""
    data = ux4_setup
    now = timezone.now()
    # Within cutoff hours (2h < 4h cutoff) so deadline_message is triggered
    booking = Booking.objects.create(
        room=data["room_auto"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="กิจกรรมใกล้เริ่ม",
        start_at=now + timedelta(hours=2),
        end_at=now + timedelta(hours=3),
        request_status=Booking.RequestStatus.APPROVED,
    )

    client.force_login(data["requester"])
    resp = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert resp.status_code == 200
    html = resp.content.decode()

    pos_hero = html.find("booking-status-hero")
    pos_deadline = html.find("booking-deadline-notice")
    pos_actions = html.find("booking-action-center")
    pos_detail = html.find("booking-detail-card")
    pos_history = html.find("booking-history-details")

    assert pos_hero != -1
    assert pos_deadline != -1
    assert pos_actions != -1
    assert pos_detail != -1
    assert pos_history != -1

    assert pos_hero < pos_deadline < pos_actions < pos_detail < pos_history
    assert html.count("booking-action-center") == 1


def test_ux4_dom_order_without_deadline(client, ux4_setup):
    """Assert DOM order hero -> action center -> booking-detail-card -> history when deadline is absent."""
    data = ux4_setup
    now = timezone.now()
    # 2 days in future (outside cutoff) so deadline_message is absent
    booking = Booking.objects.create(
        room=data["room_auto"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="กิจกรรมล่วงหน้า",
        start_at=now + timedelta(days=2),
        end_at=now + timedelta(days=2, hours=2),
        request_status=Booking.RequestStatus.APPROVED,
    )

    client.force_login(data["requester"])
    resp = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert resp.status_code == 200
    html = resp.content.decode()

    pos_hero = html.find("booking-status-hero")
    pos_actions = html.find("booking-action-center")
    pos_detail = html.find("booking-detail-card")
    pos_history = html.find("booking-history-details")

    assert pos_hero != -1
    assert pos_actions != -1
    assert pos_detail != -1
    assert pos_history != -1
    assert "booking-deadline-notice" not in html

    assert pos_hero < pos_actions < pos_detail < pos_history
    assert html.count("booking-action-center") == 1


def test_ux4_pending_approver_groups_and_actions(client, ux4_setup):
    """Approver viewing pending booking sees approve in primary group and reject in destructive group."""
    data = ux4_setup
    now = timezone.now()
    booking = Booking.objects.create(
        room=data["room_req"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="งานรออนุมัติ",
        start_at=now + timedelta(days=2),
        end_at=now + timedelta(days=2, hours=2),
        request_status=Booking.RequestStatus.PENDING,
    )

    client.force_login(data["approver"])
    resp = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert resp.status_code == 200
    html = resp.content.decode()

    assert html.count("booking-action-center") == 1
    assert "action-group-primary" in html
    assert "action-group-destructive" in html

    # Primary group: approve action present, booking_submit absent
    approve_url = reverse("approvals:approve", args=[booking.id])
    assert approve_url in html
    assert "อนุมัติคำขอ" in html
    assert reverse("bookings:booking_submit", args=[booking.id]) not in html
    assert reverse("bookings:booking_edit", args=[booking.id]) not in html

    # Destructive group: reject action present, delete_draft/cancel absent
    reject_url = reverse("approvals:reject", args=[booking.id])
    assert reject_url in html
    assert "ยืนยันการปฏิเสธ" in html
    assert reverse("bookings:booking_delete_draft", args=[booking.id]) not in html
    assert reverse("bookings:booking_cancel", args=[booking.id]) not in html

    # No duplicate action endpoints
    assert html.count(approve_url) == 1
    assert html.count(reject_url) == 1


def test_ux4_pending_requester_groups_and_actions(client, ux4_setup):
    """Requester viewing pending booking sees edit in primary and cancel in destructive group."""
    data = ux4_setup
    now = timezone.now()
    booking = Booking.objects.create(
        room=data["room_req"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="งานรออนุมัติของผู้จอง",
        start_at=now + timedelta(days=2),
        end_at=now + timedelta(days=2, hours=2),
        request_status=Booking.RequestStatus.PENDING,
    )

    client.force_login(data["requester"])
    resp = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert resp.status_code == 200
    html = resp.content.decode()

    assert html.count("booking-action-center") == 1
    assert "action-group-primary" in html
    assert "action-group-destructive" in html

    # Primary group: edit action present, approve and booking_submit absent
    edit_url = reverse("bookings:booking_edit", args=[booking.id])
    assert edit_url in html
    assert "แก้ไขรายละเอียด" in html
    assert reverse("approvals:approve", args=[booking.id]) not in html
    assert reverse("bookings:booking_submit", args=[booking.id]) not in html

    # Destructive group: cancel action present, reject and delete_draft absent
    cancel_url = reverse("bookings:booking_cancel", args=[booking.id])
    assert cancel_url in html
    assert "ยกเลิกการจอง" in html
    assert reverse("approvals:reject", args=[booking.id]) not in html
    assert reverse("bookings:booking_delete_draft", args=[booking.id]) not in html

    # Confirm dialog preserved
    assert "ยืนยันยกเลิกการจองและคืนช่วงเวลานี้ใช่หรือไม่" in html


def test_ux4_draft_requester_groups_and_actions(client, ux4_setup):
    """Requester viewing draft booking sees submit/edit in primary and delete_draft in destructive group."""
    data = ux4_setup
    now = timezone.now()
    booking = Booking.objects.create(
        room=data["room_auto"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="ร่างการจองห้อง",
        start_at=now + timedelta(days=3),
        end_at=now + timedelta(days=3, hours=2),
        request_status=Booking.RequestStatus.DRAFT,
    )

    client.force_login(data["requester"])
    resp = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert resp.status_code == 200
    html = resp.content.decode()

    assert html.count("booking-action-center") == 1
    assert "action-group-primary" in html
    assert "action-group-destructive" in html

    # Primary group: draft submit and edit present
    submit_url = reverse("bookings:booking_submit", args=[booking.id])
    edit_url = reverse("bookings:booking_edit", args=[booking.id])
    assert submit_url in html
    assert edit_url in html
    assert reverse("approvals:approve", args=[booking.id]) not in html

    # Destructive group: delete draft present, cancel absent
    delete_url = reverse("bookings:booking_delete_draft", args=[booking.id])
    assert delete_url in html
    assert "ลบร่าง" in html
    assert reverse("bookings:booking_cancel", args=[booking.id]) not in html
    assert "ลบร่างนี้ใช่หรือไม่" in html


def test_ux4_approved_requester_groups_and_actions(client, ux4_setup):
    """Requester viewing approved booking sees rebook/edit/amend in primary and cancel in destructive group."""
    data = ux4_setup
    now = timezone.now()
    booking = Booking.objects.create(
        room=data["room_auto"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="งานได้รับการอนุมัติ",
        start_at=now + timedelta(days=2),
        end_at=now + timedelta(days=2, hours=2),
        request_status=Booking.RequestStatus.APPROVED,
    )

    client.force_login(data["requester"])
    resp = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert resp.status_code == 200
    html = resp.content.decode()

    assert html.count("booking-action-center") == 1

    # Primary: rebook, edit, amend
    rebook_part = f"rebook={booking.id}"
    assert rebook_part in html
    assert "จองแบบเดิมอีกครั้ง ↻" in html
    assert reverse("bookings:booking_edit", args=[booking.id]) in html
    assert reverse("bookings:booking_amend", args=[booking.id]) in html

    # Destructive: cancel
    assert reverse("bookings:booking_cancel", args=[booking.id]) in html
    assert "ยืนยันยกเลิกการจองและคืนช่วงเวลานี้ใช่หรือไม่" in html
    assert reverse("bookings:booking_delete_draft", args=[booking.id]) not in html
    assert reverse("approvals:approve", args=[booking.id]) not in html
    assert reverse("approvals:reject", args=[booking.id]) not in html


def test_ux4_closed_no_action_status_action_center_absent_and_hero_reason(client, ux4_setup):
    """Rejected, expired, and cancelled bookings have no action center shell, and rejected displays decision_reason in hero."""
    data = ux4_setup
    now = timezone.now()

    # 1. Rejected with decision_reason
    rejected_bk = Booking.objects.create(
        room=data["room_req"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="งานถูกปฏิเสธ",
        start_at=now - timedelta(days=1),
        end_at=now - timedelta(days=1, hours=-2),
        request_status=Booking.RequestStatus.REJECTED,
        decision_reason="ห้องติดภารกิจด่วน ผบ.",
    )

    # 2. Expired
    expired_bk = Booking.objects.create(
        room=data["room_req"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="งานหมดอายุ",
        start_at=now - timedelta(days=2),
        end_at=now - timedelta(days=2, hours=-2),
        request_status=Booking.RequestStatus.EXPIRED,
    )

    # 3. Cancelled
    cancelled_bk = Booking.objects.create(
        room=data["room_auto"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="งานถูกยกเลิก",
        start_at=now + timedelta(days=1),
        end_at=now + timedelta(days=1, hours=2),
        request_status=Booking.RequestStatus.CANCELLED,
    )

    client.force_login(data["requester"])

    for bk in (rejected_bk, expired_bk, cancelled_bk):
        resp = client.get(reverse("bookings:booking_detail", args=[bk.id]))
        assert resp.status_code == 200
        html = resp.content.decode()
        # Action center must NOT render when no actions are permitted
        assert "booking-action-center" not in html
        assert "booking-detail-actions" not in html

    # Specific check for rejected decision_reason in hero
    resp_rej = client.get(reverse("bookings:booking_detail", args=[rejected_bk.id]))
    html_rej = resp_rej.content.decode()
    pos_hero = html_rej.find("booking-status-hero")
    pos_detail = html_rej.find("booking-detail-card")
    hero_section = html_rej[pos_hero:pos_detail]

    assert "status-hero-reason" in hero_section
    assert "ห้องติดภารกิจด่วน ผบ." in hero_section


def test_ux4_history_semantic_details_closed_by_default_and_complete_dom(client, ux4_setup):
    """History section uses semantic details/summary, is closed by default, and renders full history in DOM."""
    data = ux4_setup
    now = timezone.now()
    booking = Booking.objects.create(
        room=data["room_req"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="งานมีประวัติพิจารณา",
        start_at=now + timedelta(days=2),
        end_at=now + timedelta(days=2, hours=2),
        request_status=Booking.RequestStatus.APPROVED,
    )
    Approval.objects.create(
        booking=booking,
        action=Approval.Action.APPROVED,
        acted_by=data["approver"],
        acted_at=now - timedelta(hours=1),
        reason="อนุมัติตามคำขอ",
    )

    client.force_login(data["requester"])
    resp = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert resp.status_code == 200
    html = resp.content.decode()

    # Find the <details...booking-history-details...> opening tag
    match = re.search(r"<details[^>]*booking-history-details[^>]*>", html)
    assert match is not None
    details_tag = match.group(0)

    # Must NOT have 'open' attribute
    assert "open" not in details_tag

    # Summary and complete history content in DOM
    assert "ประวัติการพิจารณา" in html
    assert "history-list" in html
    assert "อนุมัติแล้ว" in html or "อนุมัติตามคำขอ" in html
    assert data["approver"].display_name in html


def test_ux4_viewer_without_permissions_sees_no_empty_action_center(client, ux4_setup):
    """A user who can view details but has no permitted actions sees no action center shell."""
    data = ux4_setup
    now = timezone.now()
    booking = Booking.objects.create(
        room=data["room_req"],
        requester=data["requester"],
        unit=data["unit"],
        responsible_name="ผู้รับผิดชอบ",
        responsible_phone="0811112222",
        title="งานของหน่วย",
        start_at=now + timedelta(days=2),
        end_at=now + timedelta(days=2, hours=2),
        request_status=Booking.RequestStatus.PENDING,
    )

    client.force_login(data["viewer"])
    resp = client.get(reverse("bookings:booking_detail", args=[booking.id]))
    assert resp.status_code == 200
    html = resp.content.decode()

    # Viewer sees full details card
    assert "booking-detail-card" in html
    # But does NOT see action center shell
    assert "booking-action-center" not in html
    assert "booking-detail-actions" not in html

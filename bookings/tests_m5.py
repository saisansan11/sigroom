from datetime import datetime, time, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from approvals.models import Approval
from approvals.services import approve_amendment, pending_for
from bookings.amendment_services import (
    apply_amendment,
    reject_amendment,
    submit_amendment,
    withdraw_amendment,
)
from bookings.models import Booking, BookingAmendment, BookingResource
from bookings.preemption_services import acknowledge, execute_preemption, replacement_options
from bookings.services import BookingConflict, can_view_details, cancel_booking, place_holds
from notifications.models import Notification
from resources.models import Resource, ResourceApprover, ResourceRule

pytestmark = pytest.mark.django_db


def _aware(day, hour=9, minute=0):
    return timezone.make_aware(datetime(2026, 8, day, hour, minute), timezone.get_current_timezone())


@pytest.fixture
def m5():
    comm = Unit.objects.create(code="COMM", name="แผนกวิชาการสื่อสาร")
    hq = Unit.objects.create(code="HQ", name="กองบังคับการ")
    requester = User.objects.create_user(
        username="somchai", email="somchai@signalschool.ac.th", password="Password-2569", unit=comm
    )
    primary = User.objects.create_user(
        username="wanida", email="wanida@signalschool.ac.th", password="Password-2569", unit=comm,
        position="ผู้อนุมัติหลัก",
    )
    other_approver = User.objects.create_user(
        username="otherapprover", email="otherapprover@signalschool.ac.th", password="Password-2569", unit=hq
    )
    outsider = User.objects.create_user(
        username="outsider", email="outsider@signalschool.ac.th", password="Password-2569", unit=hq
    )
    admin = User.objects.create_superuser(username="adminm5", email="adminm5@signalschool.ac.th", password="Password-2569")

    auto = Resource.objects.create(code="B1-201", name="ห้องเรียน 201", capacity=40, owner_unit=comm)
    ResourceRule.objects.create(resource=auto, service_start=time(7), service_end=time(21))
    required = Resource.objects.create(code="MTG-1", name="ห้องประชุม 1", capacity=40, owner_unit=comm)
    ResourceRule.objects.create(
        resource=required,
        approval_policy=ResourceRule.ApprovalPolicy.REQUIRED,
        service_start=time(7),
        service_end=time(21),
    )
    ResourceApprover.objects.create(resource=required, user=primary, is_primary=True)
    replacement = Resource.objects.create(code="B1-202", name="ห้องเรียน 202", capacity=40, owner_unit=comm)
    ResourceRule.objects.create(resource=replacement, service_start=time(7), service_end=time(21))
    other_required = Resource.objects.create(code="MTG-CO", name="ห้องประชุมกอง", capacity=40, owner_unit=hq)
    ResourceRule.objects.create(
        resource=other_required,
        approval_policy=ResourceRule.ApprovalPolicy.REQUIRED,
        service_start=time(7),
        service_end=time(21),
    )
    ResourceApprover.objects.create(resource=other_required, user=other_approver, is_primary=True)
    equipment = Resource.objects.create(
        code="PROJ-1", name="โปรเจกเตอร์", resource_type=Resource.Type.EQUIPMENT,
        room_category=Resource.Category.NONE,
    )
    ResourceRule.objects.create(resource=equipment)
    return {
        "comm": comm, "hq": hq, "requester": requester, "primary": primary,
        "other_approver": other_approver, "outsider": outsider, "admin": admin,
        "auto": auto, "required": required, "replacement": replacement,
        "other_required": other_required, "equipment": equipment,
    }


def _approved(m5, *, room=None, start=None, title="วิชาสายอากาศ"):
    start = start or _aware(27)
    booking = Booking.objects.create(
        room=room or m5["auto"], requester=m5["requester"], unit=m5["comm"],
        responsible_name="ร.อ.สมชาย", responsible_phone="0810000000", title=title,
        start_at=start, end_at=start + timedelta(hours=2), attendees=20,
        request_status=Booking.RequestStatus.APPROVED, submitted_at=_aware(24),
    )
    booking.equipment.set([m5["equipment"]])
    place_holds(booking, [m5["equipment"]])
    return booking


def _proposal(booking, m5, **overrides):
    values = {
        "room": booking.room,
        "start_at": booking.start_at + timedelta(hours=3),
        "end_at": booking.end_at + timedelta(hours=3),
        "equipment": [m5["equipment"]],
        "attendees": booking.attendees,
        "has_external": booking.has_external_attendees,
        "external_note": booking.external_attendees_note,
        "reason": "ปรับตารางสอน",
    }
    values.update(overrides)
    return values


def test_amendment_holds_full_destination_and_keeps_original(m5):
    booking = _approved(m5, room=m5["required"])
    amendment = submit_amendment(
        booking, m5["requester"], _proposal(booking, m5, room=m5["other_required"]), _aware(24)
    )
    active_main = booking.holds.filter(amendment__isnull=True, released_at__isnull=True)
    active_new = amendment.holds.filter(released_at__isnull=True)
    assert amendment.status == BookingAmendment.Status.PENDING
    assert set(active_main.values_list("resource_id", flat=True)) == {m5["required"].pk, m5["equipment"].pk}
    assert set(active_new.values_list("resource_id", flat=True)) == {m5["other_required"].pk, m5["equipment"].pk}


def test_amendment_conflict_rolls_back_without_touching_original(m5):
    booking = _approved(m5, room=m5["required"])
    other = _approved(m5, room=m5["other_required"], start=booking.start_at + timedelta(hours=3))
    before = set(booking.holds.values_list("pk", flat=True))
    with pytest.raises(BookingConflict):
        submit_amendment(
            booking, m5["requester"], _proposal(booking, m5, room=m5["other_required"]), _aware(24)
        )
    assert not booking.amendments.exists()
    assert set(booking.holds.values_list("pk", flat=True)) == before
    assert other.holds.filter(released_at__isnull=True).exists()


def test_amendment_can_overlap_own_booking_and_auto_applies(m5):
    booking = _approved(m5)
    amendment = submit_amendment(
        booking,
        m5["requester"],
        _proposal(booking, m5, start_at=booking.start_at - timedelta(hours=1), end_at=booking.end_at + timedelta(hours=1)),
        _aware(24),
    )
    booking.refresh_from_db()
    assert amendment.status == BookingAmendment.Status.APPROVED
    assert booking.start_at == _aware(27, 8) and booking.end_at == _aware(27, 12)
    assert booking.revision == 2
    assert not booking.holds.filter(amendment__isnull=False, released_at__isnull=True).exists()
    assert booking.holds.filter(amendment__isnull=True, released_at__isnull=True).count() == 2


def test_required_amendment_queue_approval_and_stale_revision_guard(m5):
    booking = _approved(m5, room=m5["required"])
    amendment = submit_amendment(booking, m5["requester"], _proposal(booking, m5), _aware(24))
    assert pending_for(m5["primary"], _aware(24))[-1].pk == amendment.pk
    booking.revision += 1
    booking.save(update_fields=["revision"])
    with pytest.raises(ValueError, match="ข้อมูลการจองเปลี่ยนไปแล้ว"):
        approve_amendment(amendment, m5["primary"], _aware(24, 10))
    amendment.refresh_from_db()
    assert amendment.status == BookingAmendment.Status.PENDING
    assert booking.holds.filter(amendment__isnull=True, released_at__isnull=True).count() == 2


def test_reject_and_withdraw_release_only_amendment_and_record_history(m5):
    booking = _approved(m5, room=m5["required"])
    amendment = submit_amendment(booking, m5["requester"], _proposal(booking, m5), _aware(24))
    with pytest.raises(ValidationError):
        reject_amendment(amendment, m5["primary"], "", _aware(24, 10))
    reject_amendment(amendment, m5["primary"], "เวลายังไม่เหมาะสม", _aware(24, 10))
    assert booking.holds.filter(amendment__isnull=True, released_at__isnull=True).count() == 2
    assert not amendment.holds.filter(released_at__isnull=True).exists()

    second = submit_amendment(booking, m5["requester"], _proposal(booking, m5), _aware(24, 11))
    withdraw_amendment(second, m5["requester"], "ขอทบทวน", _aware(24, 12))
    history = Approval.objects.get(amendment=second)
    assert history.action == Approval.Action.WITHDRAWN
    assert history.acted_by == m5["requester"] and history.reason == "ขอทบทวน"


def test_unique_pending_and_unique_active_amendment_resource_constraints(m5):
    booking = _approved(m5, room=m5["required"])
    first = submit_amendment(booking, m5["requester"], _proposal(booking, m5), _aware(24))
    with pytest.raises(ValidationError):
        submit_amendment(booking, m5["requester"], _proposal(booking, m5), _aware(24))
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BookingAmendment.objects.create(
                booking=booking, submitted_by=m5["requester"], base_revision=booking.revision
            )
    hold = first.holds.first()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BookingResource.objects.create(
                booking=booking, amendment=first, resource=hold.resource, hold=hold.hold
            )


def test_cancel_withdraws_pending_amendment_in_same_transaction(m5):
    booking = _approved(m5, room=m5["required"])
    amendment = submit_amendment(booking, m5["requester"], _proposal(booking, m5), _aware(24))
    cancel_booking(booking, m5["requester"], _aware(24))
    booking.refresh_from_db(); amendment.refresh_from_db()
    history = Approval.objects.get(amendment=amendment, action=Approval.Action.WITHDRAWN)
    assert booking.request_status == Booking.RequestStatus.CANCELLED
    assert amendment.status == BookingAmendment.Status.WITHDRAWN
    assert history.acted_by == m5["requester"]
    assert history.reason == "ถอนอัตโนมัติ: การจองถูกยกเลิก"
    assert not booking.holds.filter(released_at__isnull=True).exists()


@pytest.mark.django_db(transaction=True)
def test_composite_fk_rejects_amendment_from_another_booking(m5):
    first = _approved(m5, room=m5["required"])
    second = _approved(m5, room=m5["other_required"], start=_aware(28))
    amendment = BookingAmendment.objects.create(
        booking=first, submitted_by=m5["requester"], base_revision=first.revision
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BookingResource.objects.create(
                booking=second,
                amendment=amendment,
                resource=m5["replacement"],
                hold=first.holds.first().hold,
            )
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS fk_amendment_same_booking IMMEDIATE")


def test_preemption_permissions_execute_and_notification_privacy(m5):
    booking = _approved(m5, room=m5["required"])
    options = replacement_options(booking, m5["primary"], _aware(24))
    replacement = next(item.room for item in options if item.room == m5["replacement"])
    incoming_data = {
        "title": "ประชุมลับ ผบ.", "unit": m5["hq"], "responsible_name": "ผู้ประสานงาน",
        "responsible_phone": "082", "start_at": booking.start_at, "end_at": booking.end_at,
        "visibility": Booking.Visibility.RESTRICTED,
    }
    with pytest.raises(PermissionError):
        execute_preemption(booking, m5["outsider"], "ภารกิจเร่งด่วน", "กห 001", incoming_data, None, _aware(24))
    preemption = execute_preemption(
        booking, m5["primary"], "ภารกิจเร่งด่วน", "กห 001", incoming_data, replacement, _aware(24)
    )
    booking.refresh_from_db()
    assert booking.usage_status == Booking.UsageStatus.DISPLACED
    assert preemption.incoming.request_status == Booking.RequestStatus.APPROVED
    assert preemption.incoming.holds.filter(released_at__isnull=True).exists()
    assert preemption.replacement.request_status == Booking.RequestStatus.APPROVED
    assert can_view_details(m5["requester"], preemption.incoming) is False
    text = Notification.objects.filter(user=m5["requester"], booking=booking).latest("created_at").text
    assert "กห 001" in text and "ประชุมลับ ผบ." not in text


def test_preemption_rolls_back_everything_when_replacement_fails(m5, monkeypatch):
    booking = _approved(m5, room=m5["required"])
    incoming_data = {
        "title": "ประชุม ผบ.", "unit": m5["hq"], "responsible_name": "ผู้ประสานงาน",
        "responsible_phone": "082", "start_at": booking.start_at, "end_at": booking.end_at,
    }
    def fail(*args, **kwargs):
        raise RuntimeError("จำลองขั้น replacement ล้มเหลว")
    monkeypatch.setattr("bookings.preemption_services._copy_replacement", fail)
    with pytest.raises(RuntimeError):
        execute_preemption(
            booking, m5["primary"], "ภารกิจเร่งด่วน", "กห 002", incoming_data, m5["replacement"], _aware(24)
        )
    booking.refresh_from_db()
    assert booking.usage_status == Booking.UsageStatus.UPCOMING
    assert booking.holds.filter(released_at__isnull=True).count() == 2
    assert not booking.preemption_as_displaced.exists()


def test_required_other_owner_replacement_is_pending_urgent(m5):
    booking = _approved(m5, room=m5["required"])
    incoming_data = {
        "title": "ประชุม ผบ.", "unit": m5["hq"], "responsible_name": "ผู้ประสานงาน",
        "responsible_phone": "082", "start_at": booking.start_at, "end_at": booking.end_at,
    }
    preemption = execute_preemption(
        booking, m5["primary"], "ภารกิจเร่งด่วน", "กห 003", incoming_data, m5["other_required"], _aware(24)
    )
    assert preemption.replacement.request_status == Booking.RequestStatus.PENDING
    assert preemption.replacement.is_urgent is True
    assert Notification.objects.filter(user=m5["other_approver"], booking=preemption.replacement).exists()


def test_acknowledge_and_views_calendar_show_m5_states(client, m5):
    booking = _approved(m5, room=m5["required"])
    amendment = submit_amendment(booking, m5["requester"], _proposal(booking, m5), _aware(24))
    client.force_login(m5["requester"])
    detail = client.get(reverse("bookings:booking_detail", args=[booking.pk]))
    events = client.get(
        reverse("bookings:calendar_events"),
        {"start": _aware(26).isoformat(), "end": _aware(29).isoformat()},
    ).json()
    assert detail.status_code == 200 and "คำขอแก้ไข" in detail.content.decode()
    assert any("amendment-pending" in item.get("classNames", []) for item in events)

    withdraw_amendment(amendment, m5["requester"], now=_aware(24, 1))
    preemption = execute_preemption(
        booking, m5["primary"], "ภารกิจ", "กห 004",
        {"title": "งานเข้าแทน", "unit": m5["hq"], "responsible_name": "ผู้ประสาน", "responsible_phone": "082",
         "start_at": booking.start_at, "end_at": booking.end_at},
        None, _aware(24, 2),
    )
    acknowledge(preemption, m5["requester"], _aware(24, 3))
    preemption.refresh_from_db()
    assert preemption.acknowledged_at == _aware(24, 3)


def test_preempt_view_denies_non_primary(client, m5):
    booking = _approved(m5, room=m5["required"])
    client.force_login(m5["outsider"])
    assert client.get(reverse("bookings:booking_preempt", args=[booking.pk])).status_code == 403

from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from accounts.models import Unit, User
from approvals.models import Approval
from bookings.models import Booking, Preemption
from resources.models import Resource, ResourceApprover, ResourceRule

from .services import build_reports, parse_month


def _aware(day, hour=9):
    return timezone.make_aware(datetime(2026, 8, day, hour), timezone.get_current_timezone())


@pytest.fixture
def report_setup():
    unit = Unit.objects.create(code="REP", name="หน่วยรายงาน")
    other_unit = Unit.objects.create(code="OTHER", name="หน่วยอื่น")
    requester = User.objects.create_user("report-requester", "report-requester@signalschool.ac.th", "Test-Password-123", unit=unit)
    custodian = User.objects.create_user("report-custodian", "report-custodian@signalschool.ac.th", "Test-Password-123", unit=unit)
    outsider = User.objects.create_user("report-outsider", "report-outsider@signalschool.ac.th", "Test-Password-123", unit=other_unit)
    approver = User.objects.create_user("report-approver", "report-approver@signalschool.ac.th", "Test-Password-123", unit=unit)
    room = Resource.objects.create(code="REP-1", name="ห้องรายงาน", owner_unit=unit)
    ResourceRule.objects.create(resource=room, service_start="08:00", service_end="18:00")
    room.custodians.add(custodian)
    ResourceApprover.objects.create(resource=room, user=approver, is_primary=True)
    other_room = Resource.objects.create(code="REP-2", name="ห้องที่ไม่มีสิทธิ์", owner_unit=other_unit)
    ResourceRule.objects.create(resource=other_room)
    equipment = Resource.objects.create(code="EQ-REP", name="อุปกรณ์รายงาน", resource_type=Resource.Type.EQUIPMENT, room_category=Resource.Category.NONE, owner_unit=unit)
    ResourceRule.objects.create(resource=equipment)
    return unit, other_unit, requester, custodian, outsider, approver, room, other_room, equipment


def _booking(setup, *, start=None, status=Booking.RequestStatus.APPROVED, usage=Booking.UsageStatus.USED, room=None):
    unit, other_unit, requester, custodian, outsider, approver, default_room, other_room, equipment = setup
    start = start or _aware(10)
    return Booking.objects.create(
        room=room or default_room, requester=requester, unit=unit, responsible_name="ผู้รับผิดชอบ", responsible_phone="1234",
        title="กิจกรรมรายงาน", purpose=Booking.Purpose.MEETING, start_at=start, end_at=start + timedelta(hours=2),
        request_status=status, usage_status=usage, submitted_at=start - timedelta(hours=3),
    )


@pytest.mark.django_db
def test_room_usage_and_equipment_reports_calculate_hours(report_setup):
    booking = _booking(report_setup)
    booking.equipment.add(report_setup[8])
    start, end, label = parse_month("2569-08")
    reports = build_reports(report_setup[3], start, end)
    assert reports["room_usage"][0]["used_hours"] == 2
    assert reports["room_usage"][0]["approved_hours"] == 2
    assert reports["equipment"] == [{"equipment": "EQ-REP อุปกรณ์รายงาน", "uses": 1, "hours": 2.0}]


@pytest.mark.django_db
def test_cancellation_report_filters_unit_and_calculates_ratios(report_setup):
    _booking(report_setup, status=Booking.RequestStatus.CANCELLED, usage=Booking.UsageStatus.UPCOMING)
    _booking(report_setup, start=_aware(11), usage=Booking.UsageStatus.NO_SHOW)
    start, end, label = parse_month("2026-08")
    row = build_reports(report_setup[3], start, end, unit_id=report_setup[0].pk)["cancellation"][0]
    assert row["total"] == 2 and row["cancelled"] == 1 and row["no_show"] == 1
    assert row["combined_rate"] == 100


@pytest.mark.django_db
def test_approval_and_preemption_reports_include_amendment_compatible_history(report_setup):
    booking = _booking(report_setup)
    approval = Approval.objects.create(booking=booking, action=Approval.Action.APPROVED, acted_by=report_setup[5])
    Approval.objects.filter(pk=approval.pk).update(acted_at=_aware(10, 12))
    incoming = _booking(report_setup, start=_aware(10, 9), room=report_setup[6])
    preemption = Preemption.objects.create(
        displaced=booking, incoming=incoming, ordered_by=report_setup[5], ordered_by_position="ผู้อนุมัติ",
        reference_no="REP/001", reason="ภารกิจสำคัญ",
    )
    Preemption.objects.filter(pk=preemption.pk).update(created_at=_aware(12))
    start, end, label = parse_month("2569-08")
    reports = build_reports(report_setup[3], start, end)
    assert reports["approval"][0]["approver"] == report_setup[5].display_name
    assert reports["approval"][0]["average_hours"] == 6
    assert reports["preemption"][0]["reference_no"] == "REP/001"
    assert "2569" in reports["preemption"][0]["at"]
    assert "2026" not in reports["preemption"][0]["at"]


@pytest.mark.django_db
def test_report_permissions_room_scope_and_csv_bom(client, report_setup):
    _booking(report_setup)
    _booking(report_setup, start=_aware(11), room=report_setup[7])
    client.force_login(report_setup[3])
    response = client.get("/reports/?month=2569-08&format=csv&report=room_usage")
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    text = response.content.decode("utf-8-sig")
    assert "REP-1" in text and "REP-2" not in text


@pytest.mark.django_db
def test_regular_user_cannot_open_reports_but_assigned_approver_can(client, report_setup):
    client.force_login(report_setup[4])
    assert client.get("/reports/").status_code == 403
    client.force_login(report_setup[5])
    assert client.get("/reports/?month=2569-08").status_code == 200


@pytest.mark.django_db
def test_csv_builds_only_requested_report(client, report_setup, monkeypatch):
    _booking(report_setup)
    client.force_login(report_setup[3])
    monkeypatch.setattr(
        "reports.views.build_reports",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("ไม่ควรคำนวณครบ 5 รายงาน")),
    )
    response = client.get("/reports/?month=2569-08&format=csv&report=room_usage")
    assert response.status_code == 200

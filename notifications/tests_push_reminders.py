from datetime import datetime, timedelta

import pytest
from django.core import mail
from django.utils import timezone

from accounts.models import Unit, User
from bookings.models import Booking
from notifications.models import Notification
from notifications.reminders import send_teaching_reminders
from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def push_reminder_booking(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PUBLIC_BASE_URL = "https://sigroom.example.test"
    unit = Unit.objects.create(code="PUSH-REM-QA", name="หน่วยทดสอบ push reminder")
    teacher = User.objects.create_user(username="push-reminder-teacher", email="teacher@signalschool.ac.th", unit=unit)
    room = Resource.objects.create(code="PUSH-ONLINE-QA", name="ห้องสอนออนไลน์ push QA", room_category=Resource.Category.ONLINE)
    start = timezone.make_aware(datetime(2026, 10, 10, 9), timezone.get_current_timezone())
    return Booking.objects.create(
        room=room,
        requester=teacher,
        unit=unit,
        title="หัวข้อส่วนตัวที่ห้ามเข้า push",
        responsible_name="ครูทดสอบ",
        responsible_phone="0800000000",
        start_at=start,
        end_at=start + timedelta(hours=1),
        submitted_at=start - timedelta(days=1),
        request_status=Booking.RequestStatus.APPROVED,
        online_meeting_url="https://meet.google.com/private-link",
    )


def test_push_still_runs_after_commit_when_email_fails(push_reminder_booking, monkeypatch, django_capture_on_commit_callbacks):
    calls = []

    def failed_email(*args, **kwargs):
        raise RuntimeError("smtp secret failure")

    def fake_push(user, title, body, url):
        calls.append((user.pk, title, body, url))
        return {"sent": 1, "removed": 0, "failed": 0}

    monkeypatch.setattr("notifications.reminders.send_mail", failed_email)
    monkeypatch.setattr("notifications.push.send_push", fake_push)
    with django_capture_on_commit_callbacks(execute=True):
        counts = send_teaching_reminders(push_reminder_booking.start_at)

    assert counts["remind_start"] == 1
    assert counts["email_failed"] == 1
    assert len(calls) == 1
    user_id, title, body, url = calls[0]
    assert user_id == push_reminder_booking.requester_id
    assert title == "SIGROOM · ถึงเวลาสอนแล้ว"
    assert push_reminder_booking.title not in body
    assert push_reminder_booking.online_meeting_url not in body
    assert push_reminder_booking.online_meeting_url not in url
    assert url.endswith("/pass/")
    assert Notification.objects.filter(booking=push_reminder_booking, kind="remind_start").count() == 1


def test_push_failure_does_not_block_email_or_notification(push_reminder_booking, monkeypatch, django_capture_on_commit_callbacks, caplog):
    def failed_push(*args, **kwargs):
        raise RuntimeError("push endpoint secret")

    monkeypatch.setattr("notifications.push.send_push", failed_push)
    with django_capture_on_commit_callbacks(execute=True):
        counts = send_teaching_reminders(push_reminder_booking.start_at)

    assert counts["remind_start"] == 1
    assert counts["email_failed"] == 0
    assert len(mail.outbox) == 1
    assert Notification.objects.filter(booking=push_reminder_booking, kind="remind_start").count() == 1
    assert "teaching_reminder_push_failed" in caplog.text
    assert "push endpoint secret" not in caplog.text

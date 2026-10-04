from datetime import datetime, timedelta
from io import StringIO

import pytest
from django.core import mail
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import Unit, User
from approvals.services import run_scheduled_jobs
from bookings.models import Booking
from notifications.models import Notification
from notifications.reminders import send_teaching_reminders
from resources.models import Resource

pytestmark = pytest.mark.django_db


@pytest.fixture
def teaching_booking(settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.PUBLIC_BASE_URL = "https://sigroom.example.test"
    unit = Unit.objects.create(code="REMINDER-QA", name="หน่วยทดสอบการแจ้งเตือน")
    teacher = User.objects.create_user(
        username="reminder-teacher", email="teacher@signalschool.ac.th", unit=unit,
    )
    room = Resource.objects.create(
        code="STU-ONLINE-REMINDER", name="ห้องสอนออนไลน์ทดสอบ", room_category=Resource.Category.ONLINE,
    )
    start = timezone.make_aware(datetime(2026, 10, 10, 9), timezone.get_current_timezone())
    return Booking.objects.create(
        room=room, requester=teacher, unit=unit, title="ชื่อวิชาที่ไม่ควรเผยแพร่ในกระดิ่ง",
        responsible_name="ครูทดสอบ", responsible_phone="0800000000",
        start_at=start, end_at=start + timedelta(hours=1), submitted_at=start - timedelta(days=1),
        request_status=Booking.RequestStatus.APPROVED,
        online_meeting_url="https://meet.google.com/abc-defg-hij",
    )


@pytest.mark.parametrize(
    ("offset_minutes", "kind"),
    [(-31, None), (-30, "remind_30"), (-25, "remind_30"), (-6, "remind_30"),
     (-5, None), (-1, None), (0, "remind_start"), (5, "remind_start"),
     (9, "remind_start"), (10, None)],
)
def test_reminder_windows_have_exclusive_end(teaching_booking, django_capture_on_commit_callbacks, offset_minutes, kind):
    with django_capture_on_commit_callbacks(execute=True):
        counts = send_teaching_reminders(teaching_booking.start_at + timedelta(minutes=offset_minutes))
    assert counts == {
        "remind_30": int(kind == "remind_30"), "remind_start": int(kind == "remind_start"), "email_failed": 0,
    }
    assert list(Notification.objects.values_list("kind", flat=True)) == ([kind] if kind else [])
    assert len(mail.outbox) == int(bool(kind))


def test_three_job_runs_create_one_notification_and_email_per_round(teaching_booking, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        results = [run_scheduled_jobs(teaching_booking.start_at - timedelta(minutes=30)) for _ in range(3)]
    assert [result["remind_30"] for result in results] == [1, 0, 0]
    assert len(mail.outbox) == 1
    with django_capture_on_commit_callbacks(execute=True):
        results = [run_scheduled_jobs(teaching_booking.start_at) for _ in range(3)]
    assert [result["remind_start"] for result in results] == [1, 0, 0]
    assert Notification.objects.filter(booking=teaching_booking).count() == 2
    assert len(mail.outbox) == 2


@pytest.mark.parametrize("status", [Booking.RequestStatus.CANCELLED, Booking.RequestStatus.PENDING, Booking.RequestStatus.REJECTED, Booking.RequestStatus.EXPIRED, Booking.RequestStatus.DRAFT])
def test_non_approved_bookings_do_not_remind(teaching_booking, django_capture_on_commit_callbacks, status):
    teaching_booking.request_status = status
    teaching_booking.save(update_fields=["request_status"])
    with django_capture_on_commit_callbacks(execute=True):
        before = send_teaching_reminders(teaching_booking.start_at - timedelta(minutes=30))
        start = send_teaching_reminders(teaching_booking.start_at)
    assert before == start == {"remind_30": 0, "remind_start": 0, "email_failed": 0}
    assert not Notification.objects.exists()
    assert not mail.outbox


@pytest.mark.parametrize("category", [Resource.Category.MEETING, Resource.Category.CLASSROOM, Resource.Category.LODGING])
def test_other_room_categories_do_not_remind(teaching_booking, django_capture_on_commit_callbacks, category):
    teaching_booking.room.room_category = category
    teaching_booking.room.save(update_fields=["room_category"])
    with django_capture_on_commit_callbacks(execute=True):
        counts = send_teaching_reminders(teaching_booking.start_at)
    assert counts == {"remind_30": 0, "remind_start": 0, "email_failed": 0}
    assert not Notification.objects.exists()
    assert not mail.outbox


@pytest.mark.parametrize("usage_status", [Booking.UsageStatus.DISPLACED, Booking.UsageStatus.ROOM_UNAVAILABLE, Booking.UsageStatus.USED, Booking.UsageStatus.NO_SHOW])
def test_displaced_or_closed_usage_does_not_remind(teaching_booking, django_capture_on_commit_callbacks, usage_status):
    teaching_booking.usage_status = usage_status
    teaching_booking.save(update_fields=["usage_status"])
    with django_capture_on_commit_callbacks(execute=True):
        counts = send_teaching_reminders(teaching_booking.start_at)
    assert counts == {"remind_30": 0, "remind_start": 0, "email_failed": 0}
    assert not Notification.objects.exists()
    assert not mail.outbox


@pytest.mark.parametrize("submitted_minutes_before", [30, 29, 10])
def test_short_notice_booking_gets_only_start_reminder(teaching_booking, django_capture_on_commit_callbacks, submitted_minutes_before):
    teaching_booking.submitted_at = teaching_booking.start_at - timedelta(minutes=submitted_minutes_before)
    teaching_booking.save(update_fields=["submitted_at"])
    with django_capture_on_commit_callbacks(execute=True):
        before = send_teaching_reminders(teaching_booking.start_at - timedelta(minutes=10))
        start = send_teaching_reminders(teaching_booking.start_at)
    assert before["remind_30"] == int(submitted_minutes_before == 30)
    assert start["remind_start"] == 1
    assert len(mail.outbox) == 1 + int(submitted_minutes_before == 30)


def test_missing_submitted_at_uses_created_at(teaching_booking, django_capture_on_commit_callbacks):
    Booking.objects.filter(pk=teaching_booking.pk).update(
        submitted_at=None, created_at=teaching_booking.start_at - timedelta(minutes=10),
    )
    with django_capture_on_commit_callbacks(execute=True):
        counts = send_teaching_reminders(teaching_booking.start_at - timedelta(minutes=10))
    assert counts["remind_30"] == 0
    assert not Notification.objects.exists()


def test_email_contains_buddhist_date_time_private_link_and_canonical_pass(teaching_booking, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        send_teaching_reminders(teaching_booking.start_at - timedelta(minutes=25))
    item = Notification.objects.get()
    assert "อีก 25 นาที" in item.text
    assert "10/10/2569 09:00–10:00" in item.text
    assert teaching_booking.title not in item.text
    assert teaching_booking.online_meeting_url not in item.text
    assert item.url == f"/bookings/{teaching_booking.pk}/pass/"
    assert mail.outbox[0].to == [teaching_booking.requester.email]
    assert f"https://sigroom.example.test{item.url}" in mail.outbox[0].body
    assert teaching_booking.online_meeting_url in mail.outbox[0].body


def test_email_failure_leaves_bell_and_does_not_break_other_jobs(teaching_booking, monkeypatch, django_capture_on_commit_callbacks, caplog):
    def failed_email(*args, **kwargs):
        raise RuntimeError("sensitive-backend-error-that-must-not-be-logged")

    monkeypatch.setattr("notifications.reminders.send_mail", failed_email)
    with django_capture_on_commit_callbacks(execute=True):
        counts = run_scheduled_jobs(teaching_booking.start_at)
    assert counts["remind_start"] == counts["email_failed"] == 1
    assert "usage_used" in counts
    assert Notification.objects.filter(booking=teaching_booking, kind="remind_start").count() == 1
    assert "teaching_reminder_email_failed" in caplog.text
    assert "sensitive-backend-error" not in caplog.text
    with django_capture_on_commit_callbacks(execute=True):
        repeated = run_scheduled_jobs(teaching_booking.start_at)
    assert repeated["remind_start"] == repeated["email_failed"] == 0


@pytest.mark.parametrize("failure", ["missing_recipient", "no_delivery"])
def test_missing_recipient_or_backend_no_delivery_is_counted(teaching_booking, monkeypatch, django_capture_on_commit_callbacks, failure):
    if failure == "missing_recipient":
        teaching_booking.requester.email = ""
        teaching_booking.requester.save(update_fields=["email"])
    else:
        monkeypatch.setattr("notifications.reminders.send_mail", lambda *args, **kwargs: 0)
    with django_capture_on_commit_callbacks(execute=True):
        counts = send_teaching_reminders(teaching_booking.start_at)
    assert counts["remind_start"] == counts["email_failed"] == 1
    assert Notification.objects.exists()


def test_email_waits_for_commit_and_is_discarded_on_rollback(teaching_booking):
    with pytest.raises(ValueError), transaction.atomic():
        send_teaching_reminders(teaching_booking.start_at)
        assert not mail.outbox
        raise ValueError("rollback")
    assert not Notification.objects.exists()
    assert not mail.outbox


def test_database_constraint_preserves_ordinary_duplicate_notifications(teaching_booking):
    values = {"user": teaching_booking.requester, "booking": teaching_booking, "text": "ทดสอบ"}
    Notification.objects.create(**values)
    Notification.objects.create(**values)
    Notification.objects.create(**values, kind="remind_start")
    with pytest.raises(IntegrityError), transaction.atomic():
        Notification.objects.create(**values, kind="remind_start")
    Notification.objects.create(**values, kind="remind_30")
    assert Notification.objects.count() == 4


@pytest.mark.django_db(transaction=True)
def test_legacy_insert_without_kind_uses_database_default(teaching_booking):
    table = connection.ops.quote_name(Notification._meta.db_table)
    qn = connection.ops.quote_name
    columns = ["user_id", "text", "url", "booking_id", "created_at", "read_at"]
    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"INSERT INTO {table} ({', '.join(qn(name) for name in columns)}) VALUES ({placeholders})"
    with connection.cursor() as cursor:
        cursor.execute(
            sql,
            [
                teaching_booking.requester_id,
                "legacy notification",
                "/legacy/",
                teaching_booking.pk,
                timezone.now(),
                None,
            ],
        )
    item = Notification.objects.get(text="legacy notification")
    assert item.kind == ""


def test_notifications_remain_private_to_requester(client, teaching_booking, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        send_teaching_reminders(teaching_booking.start_at)
    outsider = User.objects.create_user(username="reminder-outsider", email="outsider@signalschool.ac.th", unit=teaching_booking.unit)
    client.force_login(outsider)
    item = Notification.objects.get()
    assert client.get(reverse("notifications:open", args=[item.pk])).status_code == 404
    assert teaching_booking.room.code not in client.get(reverse("notifications:list")).content.decode()


def test_command_reports_existing_jobs_and_reminders(teaching_booking, monkeypatch, django_capture_on_commit_callbacks):
    monkeypatch.setattr("bookings.management.commands.run_jobs.timezone.now", lambda: teaching_booking.start_at)
    output = StringIO()
    with django_capture_on_commit_callbacks(execute=True):
        call_command("run_jobs", stdout=output)
    text = output.getvalue()
    assert "หมดอายุ 0 คำขอ" in text
    assert "เตือนถึงเวลา 1" in text
    assert "อีเมลไม่สำเร็จ 0" in text


@pytest.mark.django_db(transaction=True)
def test_command_counts_email_failure_without_outer_transaction(teaching_booking, monkeypatch):
    def failed_email(*args, **kwargs):
        raise ConnectionError("SMTP ไม่พร้อม")

    monkeypatch.setattr("notifications.reminders.send_mail", failed_email)
    monkeypatch.setattr("bookings.management.commands.run_jobs.timezone.now", lambda: teaching_booking.start_at)
    output = StringIO()
    call_command("run_jobs", stdout=output)
    assert "เตือนถึงเวลา 1" in output.getvalue()
    assert "อีเมลไม่สำเร็จ 1" in output.getvalue()
    assert Notification.objects.filter(kind="remind_start").count() == 1

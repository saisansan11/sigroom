import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from datetime import datetime, time, timedelta
from django.conf import settings
from django.utils import timezone

from accounts.models import User
from bookings.lodging_models import CourseLodgingCohort
from bookings.models import Booking
from bookings.services import place_holds
from resources.models import Resource, ResourceRule

assert settings.DATABASES["default"]["NAME"] == "sigroom_audit_qa_20261003", settings.DATABASES["default"]["NAME"]

user = User.objects.get(username="audit-qa")
unit = user.unit

# Forward ordering: cohort exists first; a regular booking whose cleanup buffer reaches
# into the cohort boundary must be unavailable, while exact touching remains valid.
forward_day = timezone.localdate() + timedelta(days=9)
forward_room, _ = Resource.objects.update_or_create(
    code="QA-BUFFER-FWD",
    defaults={
        "name": "ห้องพัก QA buffer รุ่นมาก่อน",
        "resource_type": Resource.Type.ROOM,
        "room_category": Resource.Category.LODGING,
        "status": Resource.Status.ACTIVE,
    },
)
ResourceRule.objects.update_or_create(
    resource=forward_room,
    defaults={"buffer_before_min": 0, "buffer_after_min": 30},
)
forward_cohort, _ = CourseLodgingCohort.objects.update_or_create(
    slug="qa-buffer-existing",
    defaults={
        "title": "QA Buffer รุ่นจัดสรรแล้ว",
        "supervisor": user,
        "unit": unit,
        "check_in_date": forward_day,
        "check_out_date": forward_day,
        "allocation_status": CourseLodgingCohort.AllocationStatus.ALLOCATED,
        "is_active": False,
        "beds_per_room": 1,
    },
)
forward_cohort.rooms.set([forward_room])

# Reverse ordering: a regular booking hold exists first; supervisor must not be able
# to allocate a cohort whose boundary intersects that booking's cleanup buffer.
reverse_day = forward_day + timedelta(days=1)
reverse_room, _ = Resource.objects.update_or_create(
    code="QA-BUFFER-REV",
    defaults={
        "name": "ห้องพัก QA buffer การจองมาก่อน",
        "resource_type": Resource.Type.ROOM,
        "room_category": Resource.Category.LODGING,
        "status": Resource.Status.ACTIVE,
    },
)
ResourceRule.objects.update_or_create(
    resource=reverse_room,
    defaults={"buffer_before_min": 0, "buffer_after_min": 30},
)
Booking.objects.filter(title="QA reverse buffer hold", requester=user).delete()
reverse_boundary = timezone.make_aware(datetime.combine(reverse_day, time.min))
reverse_end = reverse_boundary - timedelta(minutes=15)
reverse_booking = Booking.objects.create(
    room=reverse_room,
    requester=user,
    unit=unit,
    title="QA reverse buffer hold",
    responsible_name="ผู้ทดสอบ",
    responsible_phone="0810000000",
    start_at=reverse_end - timedelta(hours=1),
    end_at=reverse_end,
)
place_holds(reverse_booking)
reverse_cohort, _ = CourseLodgingCohort.objects.update_or_create(
    slug="qa-buffer-supervisor",
    defaults={
        "title": "QA Buffer รอจัดสรร",
        "supervisor": user,
        "unit": unit,
        "check_in_date": reverse_day,
        "check_out_date": reverse_day,
        "allocation_status": CourseLodgingCohort.AllocationStatus.RELEASED,
        "is_active": False,
        "beds_per_room": 1,
    },
)
reverse_cohort.rooms.clear()

print("FORWARD_DAY", forward_day.isoformat())
print("FORWARD_ROOM", forward_room.code)
print("FORWARD_COHORT", forward_cohort.slug)
print("REVERSE_DAY", reverse_day.isoformat())
print("REVERSE_ROOM", reverse_room.code)
print("REVERSE_BOOKING", reverse_booking.pk)
print("REVERSE_COHORT_EDIT", f"/lodging/cohorts/{reverse_cohort.slug}/edit/")

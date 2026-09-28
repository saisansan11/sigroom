"""Read-only room inspection; booking services remain authoritative on submit."""
from django.db.models import Count
from django.urls import reverse

from resources.models import Resource
from .lodging_about_data import FLOOR4_LODGING_ROOMS, FLOOR5_LODGING_ROOMS
from .lodging_models import CourseLodgingCohort, CourseStudentLodging
from .lodging_services import cohort_self_booking_status


def room_details(number):
    # Only explicit inventory codes; never infer from a suffix or display name.
    if number not in FLOOR4_LODGING_ROOMS + FLOOR5_LODGING_ROOMS:
        return None
    matches = list(Resource.objects.filter(
        resource_type=Resource.Type.ROOM, room_category=Resource.Category.LODGING,
        code__in=[str(number), f"DORM-{number}"],
    ))
    if len(matches) != 1:
        return None
    room = matches[0]
    if room.floor and room.floor != str(number // 100):
        return None
    active = room.status == Resource.Status.ACTIVE
    result = {
        "id": str(room.pk), "code": room.code, "name": room.name,
        "building": room.building, "capacity": room.capacity,
        "active": active, "status": room.get_status_display(), "cohorts": [],
        "request_url": reverse("bookings:lodging_general_request") + f"?room_id={room.pk}" if active else None,
    }
    if not active:
        return result
    cohorts = [c for c in CourseLodgingCohort.objects.filter(
        rooms=room, is_active=True,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
    ).order_by("check_in_date", "title") if cohort_self_booking_status(c)[0] == "open"]
    occupied = dict(CourseStudentLodging.objects.filter(
        room=room, cohort__in=cohorts,
    ).values("cohort_id").annotate(count=Count("pk")).values_list("cohort_id", "count"))
    for cohort in cohorts:
        used = occupied.get(cohort.pk, 0)
        result["cohorts"].append({
            "title": cohort.title, "total": cohort.beds_per_room, "used": used,
            "free": max(0, cohort.beds_per_room - used),
            "dates": f"{cohort.check_in_date:%d/%m/}{cohort.check_in_date.year + 543} – {cohort.check_out_date:%d/%m/}{cohort.check_out_date.year + 543}",
            "url": reverse("bookings:lodging_portal", args=[cohort.slug]) + f"?room_id={room.pk}#room-{room.pk}",
        })
    return result

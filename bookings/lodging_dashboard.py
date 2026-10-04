"""Bounded-query staff room inventory, combining course beds and approved guest Booking Core."""
from collections import defaultdict
from datetime import datetime, time, timedelta

from django.utils import timezone
from resources.models import Resource
from .lodging_models import CourseLodgingCohort, CourseLodgingRelease, CourseStudentLodging, LodgingMeterReading, LodgingRate
from .lodging_billing import ZERO, accommodation_cost, electricity_cost, stay_nights
from .models import Booking


def room_occupancy(day):
    rooms = list(Resource.objects.filter(resource_type="room", room_category="lodging")
                 .exclude(status="retired").order_by("floor", "code"))
    cohorts = list(CourseLodgingCohort.objects.filter(allocation_status="allocated",
        check_in_date__lte=day, check_out_date__gte=day).prefetch_related("rooms"))
    students = list(CourseStudentLodging.objects.filter(cohort__in=cohorts).select_related("cohort", "lodging_rate", "room"))
    zone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), zone)
    end = start + timedelta(days=1)
    # Pending requests hold resources but are not occupants; cohort holds are not people.
    guests = list(Booking.objects.filter(room__room_category="lodging", request_status="approved",
        public_lodging_access__isnull=False, start_at__lt=end, end_at__gte=start)
        .exclude(usage_status__in=["no_show", "displaced", "room_unavailable"])
        .select_related("lodging_rate", "room", "unit"))
    meters = list(LodgingMeterReading.objects.filter(check_in_date__lte=day, check_out_date__gte=day))
    departures = list(CourseLodgingRelease.objects.filter(outcome="checked_out", released_at__gte=start,
        released_at__lt=end).values("room_id"))
    by_room = {}
    for room in rooms:
        by_room[room.pk] = {"room": room, "cooling": room.lodging_cooling,
            "capacity": room.capacity, "occupants": [], "stays": {}, "occupied": 0,
            "arrivals": 0, "departures": 0, "accommodation": ZERO, "electricity": ZERO,
            "missing_rates": 0, "estimated": False}
    for cohort in cohorts:
        for room in cohort.rooms.all():
            if room.pk in by_room:
                row = by_room[room.pk]
                row["capacity"] = max(row["capacity"], cohort.beds_per_room)
                row["stays"][(cohort.check_in_date, cohort.check_out_date)] = {
                    "check_in": cohort.check_in_date, "check_out": cohort.check_out_date, "label": cohort.title}
    for student in students:
        if student.room_id not in by_room:
            continue
        row = by_room[student.room_id]
        check_in, check_out = student.cohort.check_in_date, student.cohort.check_out_date
        row["arrivals"] += int(check_in == day)
        row["departures"] += int(check_out == day)
        if check_in <= day < check_out or check_in == check_out == day:
            row["occupants"].append({"kind": "student", "source": student, "name": f"{student.rank} {student.full_name}",
                "people": 1, "check_in": check_in, "check_out": check_out, "rate": student.lodging_rate,
                "stay_key": "cohort:" + str(student.cohort_id)})
    for booking in guests:
        if booking.room_id not in by_room:
            continue
        row = by_room[booking.room_id]
        check_in, check_out = timezone.localtime(booking.start_at).date(), timezone.localtime(booking.end_at).date()
        row["arrivals"] += booking.attendees if check_in == day else 0
        row["departures"] += booking.attendees if check_out == day else 0
        row["stays"][(check_in, check_out)] = {"check_in": check_in, "check_out": check_out, "label": "คำขอข้าราชการทหาร"}
        if check_in <= day < check_out or check_in == check_out == day:
            row["occupants"].append({"kind": "booking", "source": booking, "name": booking.responsible_name,
                "people": booking.attendees, "check_in": check_in, "check_out": check_out,
                "rate": booking.lodging_rate, "stay_key": "booking:" + str(booking.pk)})
    for departure in departures:
        if departure["room_id"] in by_room:
            by_room[departure["room_id"]]["departures"] += 1
    meters_by_room = defaultdict(list)
    for reading in meters:
        meters_by_room[reading.room_id].append(reading)
    for row in by_room.values():
        billed_rooms = set()
        group_rates = defaultdict(set)
        room_basis_stays = set()
        for occupant in row["occupants"]:
            group_rates[occupant["stay_key"]].add(occupant["rate"].pk if occupant["rate"] else None)
            if occupant["rate"] and occupant["rate"].basis == LodgingRate.Basis.ROOM:
                room_basis_stays.add(occupant["stay_key"])
        for occupant in row["occupants"]:
            row["occupied"] += occupant["people"]
            occupant["nights"] = stay_nights(occupant["check_in"], occupant["check_out"])
            rate = occupant["rate"]
            conflicting = occupant["stay_key"] in room_basis_stays and len(group_rates[occupant["stay_key"]]) > 1
            if not rate or rate.cooling != row["cooling"] or rate.effective_from > occupant["check_in"] or conflicting:
                row["missing_rates"] += occupant["people"]
                row["billing_conflict"] = bool(row.get("billing_conflict") or conflicting)
                row["estimated"] = True
                occupant["cost"] = None
                continue
            room_key = (occupant["stay_key"], rate.pk)
            occupant["cost"] = accommodation_cost(rate, occupant["check_in"], occupant["check_out"], occupant["people"])
            if rate.basis == LodgingRate.Basis.PERSON or room_key not in billed_rooms:
                row["accommodation"] += occupant["cost"]
                billed_rooms.add(room_key)
            else:
                occupant["cost"] = ZERO
            occupant["monthly_comparison"] = rate.monthly_price if occupant["nights"] > 30 else None
        if row["cooling"] == "air" and row["occupied"]:
            matched = {(occupant["check_in"], occupant["check_out"]) for occupant in row["occupants"]}
            completed = set()
            for reading in meters_by_room[row["room"].pk]:
                key = (reading.check_in_date, reading.check_out_date)
                if key not in matched:
                    continue
                amount = electricity_cost(reading)
                if amount is not None:
                    row["electricity"] += amount  # Whole-room cost, counted once regardless of people.
                    completed.add(key)
            if matched - completed:
                row["estimated"] = True
        row["total"] = row["accommodation"] + row["electricity"]
        row["free"] = max(0, row["capacity"] - row["occupied"])
        row["status"] = "empty" if not row["occupied"] else "full" if row["occupied"] >= row["capacity"] else "occupied"
        row["status_label"] = {"empty": "ว่าง", "full": "เต็ม", "occupied": "มีผู้พัก"}[row["status"]]
        row["dots"] = [n < row["occupied"] for n in range(min(row["capacity"], 60))]
        row["stays"] = list(row["stays"].values())
    return list(by_room.values())

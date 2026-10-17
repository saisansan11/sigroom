from datetime import date, timedelta
from decimal import Decimal
from accounts.models import Unit, User
from resources.models import Resource
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging, LodgingRate, LodgingMeterReading

unit, _ = Unit.objects.get_or_create(code="QA", defaults={"name": "QA Browser"})
admin, _ = User.objects.get_or_create(
    username="qaadmin",
    defaults={"email": "qaadmin@signalschool.ac.th", "unit": unit, "phone": "0810000099"},
)
admin.is_staff = True
admin.is_superuser = True
admin.is_active = True
admin.set_unusable_password()
admin.save()

room_air, _ = Resource.objects.get_or_create(
    code="QA-401",
    defaults={
        "name": "ห้อง QA 401 แอร์", "resource_type": Resource.Type.ROOM,
        "room_category": Resource.Category.LODGING, "lodging_cooling": Resource.Cooling.AIR,
        "floor": "4", "capacity": 4,
    },
)
room_fan, _ = Resource.objects.get_or_create(
    code="QA-417",
    defaults={
        "name": "ห้อง QA 417 พัดลม", "resource_type": Resource.Type.ROOM,
        "room_category": Resource.Category.LODGING, "lodging_cooling": Resource.Cooling.FAN,
        "floor": "4", "capacity": 4,
    },
)

today = date.today()
cohort, _ = CourseLodgingCohort.objects.get_or_create(
    slug="qa-browser",
    defaults={
        "title": "รุ่น QA Browser", "supervisor": admin,
        "check_in_date": today, "check_out_date": today + timedelta(days=3),
        "beds_per_room": 4, "allocation_status": CourseLodgingCohort.AllocationStatus.ALLOCATED,
        "is_active": False,
    },
)
cohort.rooms.set([room_air, room_fan])
rate_air = LodgingRate.objects.filter(cooling=Resource.Cooling.AIR).first()
rate_fan = LodgingRate.objects.filter(cooling=Resource.Cooling.FAN).first()
assert rate_air is not None and rate_fan is not None
CourseStudentLodging.objects.get_or_create(
    cohort=cohort, room=room_air, bed_number=1,
    defaults={"rank": "จ.ส.อ.", "full_name": "ผู้ทดสอบ แอร์", "origin_unit": "QA", "phone": "0811111191", "lodging_rate": rate_air},
)
CourseStudentLodging.objects.get_or_create(
    cohort=cohort, room=room_fan, bed_number=1,
    defaults={"rank": "ส.อ.", "full_name": "ผู้ทดสอบ พัดลม", "origin_unit": "QA", "phone": "0811111192", "lodging_rate": rate_fan},
)
LodgingMeterReading.objects.get_or_create(
    room=room_air, check_in_date=today, check_out_date=today + timedelta(days=3),
    defaults={"meter_in": Decimal("100.000"), "meter_out": Decimal("125.000"), "unit_price": Decimal("4.2000"), "recorded_by": admin},
)
print("QA_SEED_READY", today.isoformat(), room_air.pk, room_fan.pk)

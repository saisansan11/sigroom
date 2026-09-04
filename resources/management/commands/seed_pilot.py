"""
ใส่ข้อมูลตั้งต้นของ pilot (SRS D13): หน่วยงานตัวอย่าง, 8 ห้อง, อุปกรณ์ส่วนกลาง 2 รายการ พร้อมกฎรายห้องตามข้อ 5
รันซ้ำได้ — ถ้ามีรหัสเดิมอยู่แล้วจะไม่สร้างซ้ำ

ใช้: uv run manage.py seed_pilot
     uv run manage.py seed_pilot --demo-users
"""
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Unit, User
from bookings.lodging_models import CourseLodgingCohort, CourseStudentLodging
from bookings.lodging_services import update_cohort_allocation
from resources.models import Blackout, Resource, ResourceApprover, ResourceRule

R = Resource
P = ResourceRule.ApprovalPolicy

UNITS = [
    ("HQ", "กองบังคับการ", None),
    ("EDU", "กองการศึกษา", "HQ"),
    ("COMM", "แผนกวิชาการสื่อสาร", "EDU"),
    ("EW", "แผนกวิชาสงครามอิเล็กทรอนิกส์", "EDU"),
    ("ADMIN", "แผนกธุรการ", "HQ"),
]

# (รหัส, ชื่อ, ประเภท, หมวดห้อง, อาคาร, ชั้น, ความจุ, หน่วยเจ้าของ, นโยบาย, buffer ก่อน, buffer หลัง, อุปกรณ์ประจำห้อง)
ROOMS = [
    ("B1-101", "ห้องเรียน 101", R.Type.ROOM, R.Category.CLASSROOM, "อาคาร 1", "1", 40, "EDU", P.AUTO, 0, 0, "โปรเจกเตอร์\nกระดานไวท์บอร์ด"),
    ("B1-102", "ห้องเรียน 102", R.Type.ROOM, R.Category.CLASSROOM, "อาคาร 1", "1", 40, "EDU", P.AUTO, 0, 0, "โปรเจกเตอร์\nกระดานไวท์บอร์ด"),
    ("B1-201", "ห้องเรียน 201", R.Type.ROOM, R.Category.CLASSROOM, "อาคาร 1", "2", 60, "EDU", P.AUTO, 0, 0, "โปรเจกเตอร์\nเครื่องเสียง"),
    ("B1-202", "ห้องเรียน 202", R.Type.ROOM, R.Category.CLASSROOM, "อาคาร 1", "2", 60, "EDU", P.AUTO, 0, 0, "โปรเจกเตอร์\nเครื่องเสียง"),
    ("LAB-COMM", "ห้องปฏิบัติการสื่อสาร", R.Type.ROOM, R.Category.LAB, "อาคาร 2", "1", 24, "COMM", P.AUTO, 0, 15, "ชุดวิทยุฝึก 12 ชุด\nโปรเจกเตอร์"),
    ("LAB-EW", "ห้องปฏิบัติการ EW", R.Type.ROOM, R.Category.LAB, "อาคาร 2", "2", 20, "EW", P.AUTO, 0, 15, "ชุดฝึก ESM/ECM\nจอแสดงผล 4 จอ"),
    ("MTG-1", "ห้องประชุม 1", R.Type.ROOM, R.Category.MEETING, "อาคาร บก.", "2", 30, "HQ", P.REQUIRED, 15, 30, "ระบบประชุมออนไลน์\nเครื่องเสียง\nจอ 85 นิ้ว"),
    ("MTG-CO", "ห้องประชุมผู้บังคับบัญชา", R.Type.ROOM, R.Category.SPECIAL, "อาคาร บก.", "3", 16, "HQ", P.REQUIRED, 15, 30, "ระบบประชุมออนไลน์\nเครื่องเสียง"),
    ("DORM-101", "ห้องพัก 101 (4 เตียง)", R.Type.ROOM, R.Category.LODGING, "อาคารพัก 1", "1", 4, "HQ", P.AUTO, 0, 0, "เตียง 4 ชุด\nตู้เสื้อผ้า 4 ช่อง\nเครื่องปรับอากาศ"),
    ("DORM-102", "ห้องพัก 102 (4 เตียง)", R.Type.ROOM, R.Category.LODGING, "อาคารพัก 1", "1", 4, "HQ", P.AUTO, 0, 0, "เตียง 4 ชุด\nตู้เสื้อผ้า 4 ช่อง\nเครื่องปรับอากาศ"),
    ("DORM-103", "ห้องพัก 103 (4 เตียง)", R.Type.ROOM, R.Category.LODGING, "อาคารพัก 1", "1", 4, "HQ", P.AUTO, 0, 0, "เตียง 4 ชุด\nตู้เสื้อผ้า 4 ช่อง\nเครื่องปรับอากาศ"),
    ("DORM-104", "ห้องพัก 104 (4 เตียง)", R.Type.ROOM, R.Category.LODGING, "อาคารพัก 1", "1", 4, "HQ", P.AUTO, 0, 0, "เตียง 4 ชุด\nตู้เสื้อผ้า 4 ช่อง\nเครื่องปรับอากาศ"),
    ("PROJ-01", "โปรเจกเตอร์พกพา 1", R.Type.EQUIPMENT, R.Category.NONE, "คลังอุปกรณ์", "", 0, "ADMIN", P.AUTO, 0, 0, ""),
    ("VC-KIT-01", "ชุดประชุมออนไลน์เคลื่อนที่ 1", R.Type.EQUIPMENT, R.Category.NONE, "คลังอุปกรณ์", "", 0, "ADMIN", P.AUTO, 0, 0, ""),
]


class Command(BaseCommand):
    help = "ใส่ข้อมูลตั้งต้น pilot: หน่วยงาน 5 หน่วย ห้อง 8 ห้อง อุปกรณ์ส่วนกลาง 2 รายการ"

    def add_arguments(self, parser):
        parser.add_argument(
            "--demo-users",
            action="store_true",
            help="สร้างบัญชี somchai, wanida และ somsak สำหรับทดลอง M2–M4",
        )

    def handle(self, *args, **options):
        units = {}
        for code, name, parent in UNITS:
            unit, created = Unit.objects.get_or_create(code=code, defaults={"name": name, "parent": units.get(parent)})
            units[code] = unit
            self.stdout.write(f"{'สร้าง' if created else 'มีแล้ว'} หน่วย {code} {name}")

        for code, name, rtype, cat, building, floor, cap, owner, policy, bb, ba, equip in ROOMS:
            res, created = Resource.objects.get_or_create(
                code=code,
                defaults=dict(
                    name=name, resource_type=rtype, room_category=cat, building=building, floor=floor,
                    capacity=cap, owner_unit=units[owner], fixed_equipment=equip,
                ),
            )
            ResourceRule.objects.get_or_create(
                resource=res, defaults=dict(approval_policy=policy, buffer_before_min=bb, buffer_after_min=ba)
            )
            if code == "MTG-CO":
                res.rule.allowed_units.set([units["HQ"]])  # ห้องผู้บังคับบัญชา: เฉพาะหน่วยที่กำหนด (O4 ค่าชั่วคราว)
            self.stdout.write(f"{'สร้าง' if created else 'มีแล้ว'} {code} {name} [{ResourceRule.ApprovalPolicy(policy).label}]")

        if options["demo_users"]:
            demo_users = (
                ("somchai", "สมชาย", "ใจดี", "ร.อ.", "COMM"),
                ("wanida", "วนิดา", "มั่นคง", "ร.อ.", "EW"),
                ("somsak", "สมศักดิ์", "พร้อมรบ", "พ.ต.", "HQ"),
            )
            users = {}
            for username, first_name, last_name, rank, unit_code in demo_users:
                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        "email": f"{username}@signalschool.ac.th",
                        "first_name": first_name,
                        "last_name": last_name,
                        "rank": rank,
                        "unit": units[unit_code],
                    },
                )
                if created:
                    user.set_password("Demo-Sigroom-2569")
                    user.must_change_password = True
                    user.save()
                users[username] = user
                self.stdout.write(f"{'สร้าง' if created else 'มีแล้ว (ไม่เปลี่ยนรหัส)'} บัญชีทดลอง {username}")

            meeting_room = Resource.objects.get(code="MTG-1")
            ResourceApprover.objects.update_or_create(
                resource=meeting_room,
                user=users["wanida"],
                defaults={"is_primary": True},
            )
            self.stdout.write("กำหนด wanida เป็นผู้อนุมัติหลักของ MTG-1")

            command_room = Resource.objects.get(code="MTG-CO")
            ResourceApprover.objects.update_or_create(
                resource=command_room,
                user=users["somsak"],
                defaults={"is_primary": True},
            )
            ResourceApprover.objects.update_or_create(
                resource=meeting_room,
                user=users["somsak"],
                defaults={"is_primary": False},
            )
            self.stdout.write("กำหนด somsak เป็นผู้อนุมัติหลักของ MTG-CO และผู้อนุมัติสำรองของ MTG-1")

        today = timezone.localdate()
        days_to_monday = (7 - today.weekday()) % 7 or 7
        next_monday = today + timedelta(days=days_to_monday)
        zone = timezone.get_current_timezone()
        blackout_start = timezone.make_aware(datetime.combine(next_monday, time.min), zone)
        Blackout.objects.update_or_create(
            title="วันหยุดชดเชย",
            defaults={
                "start_at": blackout_start,
                "end_at": blackout_start + timedelta(days=1),
                "scope": Blackout.Scope.ALL,
                "building": "",
                "room_category": "",
            },
        )
        self.stdout.write("เพิ่มปฏิทินส่วนกลางตัวอย่าง: วันหยุดชดเชย (วันจันทร์หน้า)")

        # เพิ่มรอบจองที่พักหลักสูตรตัวอย่างผ่าน service กลาง ไม่ bypass allocation guard
        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        if admin_user:
            cohort, created = CourseLodgingCohort.objects.get_or_create(
                slug="nr-70",
                defaults={
                    "title": "หลักสูตรชั้นนายร้อย เหล่า ส. รุ่นที่ 70",
                    "supervisor": admin_user,
                    "unit": units.get("EDU"),
                    "check_in_date": today + timedelta(days=7),
                    "check_out_date": today + timedelta(days=67),
                    "beds_per_room": 4,
                    "allocation_status": CourseLodgingCohort.AllocationStatus.RELEASED,
                    "is_active": False,
                    "note": "ขอให้นักเรียนทุกคนรายงานตัวก่อนเวลา 18:00 น. ของวันเปิดหลักสูตร และเตรียมเครื่องนอนส่วนตัวมาด้วย",
                },
            )
            dorm_rooms = Resource.objects.filter(code__in=["DORM-101", "DORM-102", "DORM-103", "DORM-104"])
            cohort = update_cohort_allocation(
                cohort=cohort,
                rooms=dorm_rooms,
                check_in_date=today + timedelta(days=7),
                check_out_date=today + timedelta(days=67),
                allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
                is_active=True,
                beds_per_room=4,
                supervisor=admin_user,
                title="หลักสูตรชั้นนายร้อย เหล่า ส. รุ่นที่ 70",
                note="ขอให้นักเรียนทุกคนรายงานตัวก่อนเวลา 18:00 น. ของวันเปิดหลักสูตร และเตรียมเครื่องนอนส่วนตัวมาด้วย",
            )

            # ใส่ตัวอย่างนักเรียน 2 นายในห้อง DORM-101
            d101 = dorm_rooms.filter(code="DORM-101").first()
            if d101:
                CourseStudentLodging.objects.get_or_create(
                    cohort=cohort,
                    room=d101,
                    bed_number=1,
                    defaults={
                        "rank": "ร.ท.",
                        "full_name": "ชัยยศ ยอดกล้า",
                        "origin_unit": "ส.พัน.1 รอ.",
                        "phone": "081-444-5555",
                    },
                )
                CourseStudentLodging.objects.get_or_create(
                    cohort=cohort,
                    room=d101,
                    bed_number=2,
                    defaults={
                        "rank": "ร.ท.",
                        "full_name": "พงษ์ศักดิ์ ภักดี",
                        "origin_unit": "ส.พัน.12 พล.ม.2 รอ.",
                        "phone": "082-666-7777",
                    },
                )
            self.stdout.write(f"{'สร้าง' if created else 'มีแล้ว'} รอบจองที่พักตัวอย่าง: หลักสูตรชั้นนายร้อย รุ่นที่ 70 (ลิงก์: /lodging/c/nr-70/)")

        self.stdout.write(self.style.SUCCESS("เสร็จ — เปิด http://127.0.0.1:8000/ เพื่อดู SIGROOM"))

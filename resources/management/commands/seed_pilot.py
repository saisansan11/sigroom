"""
ใส่ข้อมูลตั้งต้นของ pilot (SRS D13): หน่วยงานตัวอย่าง, 8 ห้อง, อุปกรณ์ส่วนกลาง 2 รายการ พร้อมกฎรายห้องตามข้อ 5
รันซ้ำได้ — ถ้ามีรหัสเดิมอยู่แล้วจะไม่สร้างซ้ำ

ใช้: uv run manage.py seed_pilot
"""
from django.core.management.base import BaseCommand

from accounts.models import Unit
from resources.models import Resource, ResourceRule

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
    ("PROJ-01", "โปรเจกเตอร์พกพา 1", R.Type.EQUIPMENT, R.Category.NONE, "คลังอุปกรณ์", "", 0, "ADMIN", P.AUTO, 0, 0, ""),
    ("VC-KIT-01", "ชุดประชุมออนไลน์เคลื่อนที่ 1", R.Type.EQUIPMENT, R.Category.NONE, "คลังอุปกรณ์", "", 0, "ADMIN", P.AUTO, 0, 0, ""),
]


class Command(BaseCommand):
    help = "ใส่ข้อมูลตั้งต้น pilot: หน่วยงาน 5 หน่วย ห้อง 8 ห้อง อุปกรณ์ส่วนกลาง 2 รายการ"

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

        self.stdout.write(self.style.SUCCESS("เสร็จ — เปิด http://127.0.0.1:8000/admin/resources/resource/ เพื่อดู"))

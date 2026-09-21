"""Idempotent setup for the three online teaching rooms and teacher role.

This command prepares configuration only.  It never creates bookings and it does not
perform a deployment. Existing incompatible room records fail closed instead of being
silently repurposed.
"""
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Unit, User
from bookings.management.commands.seed_courses import COURSES
from bookings.models import ReferenceValue
from bookings.online_teaching import ONLINE_TEACHER_GROUP, ONLINE_TEACHING_ROOM_CODES
from resources.models import Resource, ResourceRule


ROOM_SPECS = (
    ("STU-ONLINE-1", "ห้องสอนออนไลน์ 1"),
    ("STU-ONLINE-2", "ห้องสอนออนไลน์ 2"),
    ("STU-ONLINE-3", "ห้องสอนออนไลน์ 3"),
)
EQUIPMENT = "กล้อง\nไมโครโฟน\nไฟสตูดิโอ\nจอเขียว"


class Command(BaseCommand):
    help = "ตั้งค่าห้องสอนออนไลน์ 3 ห้อง + role ครู + รายการหลักสูตรแบบ idempotent"

    def add_arguments(self, parser):
        parser.add_argument("--owner-unit", default="EDU", help="รหัสหน่วยเจ้าของห้อง (ค่าเริ่มต้น EDU)")
        parser.add_argument(
            "--teacher",
            action="append",
            default=[],
            help="username ครูที่จะเพิ่มเข้า role signalschool-teacher; ระบุซ้ำได้",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            owner_unit = Unit.objects.get(code=options["owner_unit"], is_active=True)
        except Unit.DoesNotExist as exc:
            raise CommandError(f"ไม่พบหน่วยที่เปิดใช้ code={options['owner_unit']}") from exc

        teacher_group, _ = Group.objects.get_or_create(name=ONLINE_TEACHER_GROUP)

        for code, name in ROOM_SPECS:
            resource, created = Resource.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "resource_type": Resource.Type.ROOM,
                    "room_category": Resource.Category.ONLINE,
                    "building": "อาคาร บก.กศ.",
                    "floor": "1",
                    "capacity": 5,
                    "owner_unit": owner_unit,
                    "fixed_equipment": EQUIPMENT,
                    "status": Resource.Status.ACTIVE,
                },
            )
            if resource.resource_type != Resource.Type.ROOM or resource.room_category != Resource.Category.ONLINE:
                raise CommandError(f"{code} มีอยู่แล้วแต่ไม่ใช่ห้องสอนออนไลน์ — หยุดเพื่อป้องกันการเปลี่ยนประเภทโดยไม่ตั้งใจ")
            if resource.status != Resource.Status.ACTIVE:
                raise CommandError(f"{code} ยังไม่อยู่สถานะใช้งาน — ไม่เปิดห้องโดยอัตโนมัติ")
            if resource.owner_unit_id and resource.owner_unit_id != owner_unit.pk:
                raise CommandError(f"{code} มีหน่วยเจ้าของต่างจาก {owner_unit.code} — หยุดเพื่อให้ผู้ดูแลตรวจสอบ")
            rule, rule_created = ResourceRule.objects.get_or_create(
                resource=resource,
                defaults={
                    "approval_policy": ResourceRule.ApprovalPolicy.AUTO,
                    "buffer_before_min": 0,
                    "buffer_after_min": 15,
                },
            )
            if rule.approval_policy != ResourceRule.ApprovalPolicy.AUTO:
                raise CommandError(f"{code} ตั้งนโยบายเป็นต้องอนุมัติ จึงไม่พร้อมสำหรับ Teacher Self-Service")
            self.stdout.write(f"{'สร้าง' if created else 'มีแล้ว'} {code} {resource.name}")
            if rule_created:
                self.stdout.write(f"  สร้างนโยบาย AUTO สำหรับ {code}")

        actual_codes = set(
            Resource.objects.filter(
                code__in=ONLINE_TEACHING_ROOM_CODES,
                resource_type=Resource.Type.ROOM,
                room_category=Resource.Category.ONLINE,
            ).values_list("code", flat=True)
        )
        if actual_codes != set(ONLINE_TEACHING_ROOM_CODES):
            raise CommandError("ตั้งค่าห้องสอนออนไลน์ไม่ครบ 3 ห้อง")

        for title, _slug, _start, _end in COURSES:
            ReferenceValue.objects.get_or_create(
                field="attendee_level",
                value=title,
                defaults={"order": 100},
            )

        teacher_usernames = options["teacher"]
        if isinstance(teacher_usernames, str):
            teacher_usernames = [teacher_usernames]
        for username in teacher_usernames:
            try:
                user = User.objects.get(username=username, is_active=True)
            except User.DoesNotExist as exc:
                raise CommandError(f"ไม่พบผู้ใช้ที่เปิดใช้งาน username={username}") from exc
            user.groups.add(teacher_group)
            self.stdout.write(f"เพิ่มสิทธิ์ครูให้ {username}")

        self.stdout.write(self.style.SUCCESS("ตั้งค่าห้องสอนออนไลน์ 3 ห้องและ Course Catalog เรียบร้อย"))

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from accounts.models import User
from bookings.lodging_models import CourseLodgingCohort
from bookings.lodging_services import can_create_cohort, update_cohort_allocation
from bookings.models import ReferenceValue


COURSES = (
    ("นนส. เหล่า ส. (ระยะเวลา 8 เดือน) รุ่นที่ 29/68", "nns-29-68", "2026-03-02", "2026-10-30"),
    ("นนส.ทบ. 1 ปี 6 เดือน เหล่า ส. (ระยะเวลา 8 เดือน) รุ่นที่ 30/69", "nns-30-69", "2027-03-01", "2027-10-29"),
    ("ชั้นนายพัน เหล่า ส. รุ่นที่ 64", "np-64", "2026-10-20", "2027-02-24"),
    ("ชั้นนายพัน เหล่า ส. รุ่นที่ 65", "np-65", "2027-04-21", "2027-08-24"),
    ("ชั้นนายร้อย เหล่า ส. รุ่นที่ 71", "nr-71", "2027-05-31", "2027-09-07"),
    ("นายสิบอาวุโส เหล่า ส. ผ่านสื่ออิเล็กทรอนิกส์ (หลักสูตรเร่งรัด) รุ่นที่ 11", "snr-nco-11", "2026-11-02", "2027-03-05"),
    ("นายสิบอาวุโส เหล่า ส. ผ่านสื่ออิเล็กทรอนิกส์ (หลักสูตรเร่งรัด) รุ่นที่ 12", "snr-nco-12", "2026-11-23", "2027-03-05"),
    ("นายสิบอาวุโส เหล่า ส. ผ่านสื่ออิเล็กทรอนิกส์ (หลักสูตรเร่งรัด) รุ่นที่ 13", "snr-nco-13", "2027-04-26", "2027-08-06"),
    ("นายสิบชั้นต้น เหล่า ส. ผ่านสื่ออิเล็กทรอนิกส์ (หลักสูตรเร่งรัด) รุ่นที่ 11", "jnr-nco-11", "2026-10-06", "2026-12-25"),
    ("นายสิบชั้นต้น เหล่า ส. ผ่านสื่ออิเล็กทรอนิกส์ (หลักสูตรเร่งรัด) รุ่นที่ 12", "jnr-nco-12", "2026-11-09", "2027-01-29"),
    ("ช่างอิเล็กทรอนิกส์ รุ่นที่ 23", "tech-23", "2025-11-04", "2026-10-30"),
    ("ช่างอิเล็กทรอนิกส์ รุ่นที่ 24", "tech-24", "2026-11-03", "2027-10-29"),
    ("การฝึกอบรมช่างภาพสนาม รุ่นที่ 9", "cameraman-9", "2027-06-14", "2027-06-25"),
    ("ทักษะด้านดิจิทัลของนายทหารประทวน รุ่นที่ 8", "digital-nco-8", "2027-06-07", "2027-07-09"),
)


class Command(BaseCommand):
    help = "นำเข้าข้อมูล 14 หลักสูตรสำหรับระบบที่พักหลักสูตร โดยไม่จัดสรรห้องอัตโนมัติ"

    def add_arguments(self, parser):
        parser.add_argument(
            "--default-supervisor",
            help="username ผู้กำกับหลักสูตรที่จะใช้เมื่อสร้างข้อมูลใหม่",
        )

    def _resolve_supervisor(self, username):
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist as exc:
                raise CommandError(f"ไม่พบผู้ใช้ username={username}") from exc
            if not can_create_cohort(user):
                raise CommandError(f"ผู้ใช้ {username} ไม่มีสิทธิ์เป็นผู้กำกับหลักสูตร")
            return user

        candidates = User.objects.filter(
            Q(is_superuser=True) | Q(is_staff=True) | Q(unit__isnull=False)
        ).distinct()
        if candidates.count() != 1:
            raise CommandError(
                "กรุณาระบุ --default-supervisor <username> เมื่อผู้ใช้ที่มีสิทธิ์มีไม่เท่ากับ 1 คน"
            )
        return candidates.first()

    def handle(self, *args, **options):
        supervisor = self._resolve_supervisor(options.get("default_supervisor"))
        for title, slug, start_text, end_text in COURSES:
            check_in_date = date.fromisoformat(start_text)
            check_out_date = date.fromisoformat(end_text)
            with transaction.atomic():
                cohort, created = CourseLodgingCohort.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "title": title,
                        "supervisor": supervisor,
                        "unit": supervisor.unit,
                        "check_in_date": check_in_date,
                        "check_out_date": check_out_date,
                        "beds_per_room": 4,
                        "allocation_status": CourseLodgingCohort.AllocationStatus.RELEASED,
                        "is_active": False,
                    },
                )
                old_status = cohort.allocation_status
                old_rooms = list(cohort.rooms.all())
                try:
                    update_cohort_allocation(
                        cohort=cohort,
                        rooms=old_rooms,
                        check_in_date=check_in_date,
                        check_out_date=check_out_date,
                        allocation_status=old_status,
                        is_active=cohort.is_active,
                        beds_per_room=cohort.beds_per_room,
                        supervisor=cohort.supervisor or supervisor,
                        title=title,
                        note=cohort.note,
                    )
                except ValidationError as exc:
                    if old_status == CourseLodgingCohort.AllocationStatus.ALLOCATED:
                        self.stdout.write(
                            self.style.WARNING(
                                f"DRIFT {slug}: ไม่อัปเดตข้อมูลรุ่นที่จัดสรรแล้ว ({exc}) — คงข้อมูลเดิมไว้"
                            )
                        )
                    else:
                        raise
                else:
                    self.stdout.write(f"{'สร้าง' if created else 'อัปเดต'} หลักสูตร {slug}: {title}")

            ReferenceValue.objects.get_or_create(
                field="attendee_level",
                value=title,
                defaults={"order": 100},
            )

        self.stdout.write(self.style.SUCCESS(f"นำเข้า/ตรวจสอบหลักสูตรครบ {len(COURSES)} รายการแล้ว"))

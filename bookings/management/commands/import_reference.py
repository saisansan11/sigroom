from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bookings.models import ReferenceValue
from bookings.services import FREQUENT_FIELDS


class Command(BaseCommand):
    help = "นำเข้าค่าอ้างอิงสำหรับ datalist จากไฟล์ข้อความ UTF-8 หนึ่งค่าต่อบรรทัด"

    def add_arguments(self, parser):
        parser.add_argument("field", help="ชื่อฟิลด์ เช่น title")
        parser.add_argument("text_file", help="ไฟล์ข้อความ UTF-8 หนึ่งค่าต่อบรรทัด")

    def handle(self, *args, **options):
        field = options["field"]
        if field not in FREQUENT_FIELDS:
            raise CommandError("field ไม่ถูกต้อง: " + field)
        source = Path(options["text_file"])
        if not source.is_file():
            raise CommandError(f"ไม่พบไฟล์ {source}")

        created = 0
        skipped = 0
        seen = set()
        for raw in source.read_text(encoding="utf-8-sig").splitlines():
            value = raw.strip()
            if not value or value in seen:
                if value:
                    skipped += 1
                continue
            seen.add(value)
            _, was_created = ReferenceValue.objects.get_or_create(field=field, value=value)
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(f"นำเข้าค่าอ้างอิงสำเร็จ: สร้าง {created} · ข้าม {skipped}"))

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Unit


REQUIRED_COLUMNS = ("code", "name", "parent")


class Command(BaseCommand):
    help = "นำเข้าหรืออัปเดตหน่วยงานจาก CSV โดยผูกหน่วยเหนือด้วยรหัสหน่วย"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="ไฟล์ CSV UTF-8(-sig) หัวคอลัมน์ code,name,parent")

    def handle(self, *args, **options):
        source = Path(options["csv_file"])
        if not source.is_file():
            raise CommandError(f"ไม่พบไฟล์ {source}")

        rows = []
        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            missing = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or [])]
            if missing:
                raise CommandError("หัวคอลัมน์ไม่ครบ: " + ", ".join(missing))
            for row_number, raw in enumerate(reader, start=2):
                row = {key: (raw.get(key) or "").strip() for key in REQUIRED_COLUMNS}
                if not any(row.values()):
                    continue
                if not row["code"] or not row["name"]:
                    raise CommandError(f"แถว {row_number}: ต้องมี code และ name")
                rows.append((row_number, row))

        if not rows:
            self.stdout.write(self.style.WARNING("ไม่มีข้อมูลหน่วยงานให้นำเข้า"))
            return

        file_codes = {row["code"] for _, row in rows}
        parent_codes = {row["parent"] for _, row in rows if row["parent"]}
        existing_parent_codes = set(Unit.objects.filter(code__in=parent_codes).values_list("code", flat=True))
        missing_parents = sorted(parent_codes - file_codes - existing_parent_codes)
        if missing_parents:
            raise CommandError("ไม่พบรหัสหน่วยแม่: " + ", ".join(missing_parents))

        created = 0
        updated = 0
        with transaction.atomic():
            # รอบแรกสร้าง/อัปเดตทุกหน่วยก่อน เพื่อให้ parent ที่อยู่ท้ายไฟล์อ้างถึงได้
            for _, row in rows:
                unit, was_created = Unit.objects.update_or_create(
                    code=row["code"],
                    defaults={"name": row["name"]},
                )
                created += int(was_created)
                updated += int(not was_created)

            units = {item.code: item for item in Unit.objects.filter(code__in=file_codes | parent_codes)}
            # รอบสองค่อยผูก parent ตามข้อมูลในไฟล์
            for row_number, row in rows:
                unit = units[row["code"]]
                parent = units.get(row["parent"]) if row["parent"] else None
                if row["parent"] and parent is None:
                    raise CommandError(f"แถว {row_number}: ไม่พบหน่วยแม่รหัส {row['parent']}")
                if unit.parent_id != getattr(parent, "pk", None):
                    unit.parent = parent
                    unit.save(update_fields=["parent"])

        self.stdout.write(self.style.SUCCESS(f"นำเข้าหน่วยงานสำเร็จ: สร้าง {created} · อัปเดต {updated} · รวม {len(rows)} แถว"))

import csv
import secrets
import string
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Unit, User, validate_allowed_email_domain


REQUIRED_COLUMNS = (
    "username",
    "email",
    "rank",
    "first_name",
    "last_name",
    "unit_code",
    "phone",
    "service_number",
)


def initial_password(length=12):
    alphabet = string.ascii_letters + string.digits + "-_!"
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.islower() for c in value) and any(c.isupper() for c in value) and any(c.isdigit() for c in value):
            return value


class Command(BaseCommand):
    help = "นำเข้าบัญชีจริงจาก CSV และออกไฟล์รหัสเริ่มต้นสำหรับผู้ดูแลแจกด้วยมือ"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="ไฟล์ CSV UTF-8 ที่มีหัวคอลัมน์ตามแม่แบบ")
        parser.add_argument("--output-dir", default=".", help="โฟลเดอร์เก็บไฟล์รหัสเริ่มต้น (ค่าเริ่มต้น: โฟลเดอร์ปัจจุบัน)")

    def handle(self, *args, **options):
        source = Path(options["csv_file"])
        if not source.is_file():
            raise CommandError(f"ไม่พบไฟล์ {source}")
        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        units = {item.code: item for item in Unit.objects.filter(is_active=True)}
        created_credentials = []
        skipped = 0

        with source.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            missing = [name for name in REQUIRED_COLUMNS if name not in (reader.fieldnames or [])]
            if missing:
                raise CommandError("หัวคอลัมน์ไม่ครบ: " + ", ".join(missing))
            for row_number, raw in enumerate(reader, start=2):
                row = {key: (raw.get(key) or "").strip() for key in REQUIRED_COLUMNS}
                errors = []
                if not row["username"]:
                    errors.append("ไม่มี username")
                if not row["email"]:
                    errors.append("ไม่มี email")
                else:
                    try:
                        validate_allowed_email_domain(row["email"])
                    except ValidationError as exc:
                        errors.extend(exc.messages)
                unit = units.get(row["unit_code"])
                if not unit:
                    errors.append(f"ไม่พบหน่วยที่เปิดใช้รหัส {row['unit_code'] or '-'}")
                if User.objects.filter(username__iexact=row["username"]).exists():
                    errors.append("username ซ้ำกับบัญชีเดิม")
                if User.objects.filter(email__iexact=row["email"]).exists():
                    errors.append("email ซ้ำกับบัญชีเดิม")
                if row["service_number"] and User.objects.filter(service_number=row["service_number"]).exists():
                    errors.append("หมายเลขประจำตัวซ้ำกับบัญชีเดิม")
                if errors:
                    skipped += 1
                    self.stderr.write(f"ข้ามแถว {row_number} ({row['username'] or '-'}): " + "; ".join(errors))
                    continue

                password = initial_password()
                try:
                    with transaction.atomic():
                        user = User(
                            username=row["username"],
                            email=row["email"].lower(),
                            rank=row["rank"],
                            first_name=row["first_name"],
                            last_name=row["last_name"],
                            unit=unit,
                            phone=row["phone"],
                            service_number=row["service_number"] or None,
                            must_change_password=True,
                        )
                        user.set_password(password)
                        user.full_clean()
                        user.save()
                except ValidationError as exc:
                    skipped += 1
                    self.stderr.write(f"ข้ามแถว {row_number} ({row['username']}): " + "; ".join(exc.messages))
                    continue
                created_credentials.append((user.username, password))
                self.stdout.write(f"สร้างบัญชี {user.username} ({unit.code})")

        output_path = output_dir / f"imported-users-{date.today():%Y%m%d}.csv"
        with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["username", "รหัสเริ่มต้น"])
            writer.writerows(created_credentials)
        self.stdout.write(self.style.WARNING("คำเตือน: ไฟล์นี้มีรหัสผ่าน อ่านได้โดยตรง ให้แจกด้วยมือและลบทิ้งทันทีหลังแจกครบ"))
        self.stdout.write(self.style.SUCCESS(f"สร้าง {len(created_credentials)} บัญชี · ข้าม {skipped} แถว · ไฟล์รหัส: {output_path.resolve()}"))


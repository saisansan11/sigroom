import getpass
import sys
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from accounts.services import reset_password_by_superuser


MAX_SECRET_BYTES = 4096


def _clean_secret(raw: str) -> str:
    value = raw.rstrip("\r\n")
    if not value:
        raise CommandError("รหัสผ่านชั่วคราวว่างเปล่า")
    if "\n" in value or "\r" in value:
        raise CommandError("รหัสผ่านชั่วคราวต้องมีเพียง 1 บรรทัด")
    return value


class Command(BaseCommand):
    help = "รีเซ็ตรหัสผ่านบัญชีเดียวแบบ audited และบังคับเปลี่ยนรหัสเมื่อเข้าสู่ระบบครั้งถัดไป"

    def add_arguments(self, parser):
        parser.add_argument("username", help="username ของบัญชีที่จะรีเซ็ต")
        parser.add_argument(
            "--operator",
            required=True,
            help="username ของ active superuser ผู้อนุมัติ/ดำเนินการ",
        )
        secret_source = parser.add_mutually_exclusive_group()
        secret_source.add_argument(
            "--password-file",
            help="ไฟล์ UTF-8 ที่มีรหัสผ่านชั่วคราว 1 บรรทัด; ไม่ควรอยู่ใน repository",
        )
        secret_source.add_argument(
            "--password-stdin",
            action="store_true",
            help="อ่านรหัสผ่านชั่วคราวจาก stdin; หากเป็น TTY จะใช้ secure prompt",
        )
        parser.add_argument(
            "--confirm",
            help="ต้องตรงกับ RESET:<username> ก่อนมีการเขียนข้อมูล",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="ตรวจ operator/target เท่านั้น ไม่อ่าน secret และไม่เขียนฐานข้อมูล",
        )

    def _resolve_user(self, username: str, *, role: str) -> User:
        try:
            return User.objects.get(username=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"ไม่พบ {role} username={username}") from exc

    def _read_password(self, options) -> str:
        password_file = options.get("password_file")
        password_stdin = bool(options.get("password_stdin"))
        if not password_file and not password_stdin:
            raise CommandError("ต้องระบุ --password-file หรือ --password-stdin")

        if password_file:
            source = Path(password_file)
            if not source.is_file():
                raise CommandError(f"ไม่พบไฟล์รหัสผ่าน {source}")
            if source.stat().st_size > MAX_SECRET_BYTES:
                raise CommandError("ไฟล์รหัสผ่านมีขนาดเกินขอบเขตที่อนุญาต")
            try:
                raw = source.read_text(encoding="utf-8")
            except OSError as exc:
                raise CommandError(f"อ่านไฟล์รหัสผ่านไม่ได้: {exc}") from exc
            return _clean_secret(raw)

        if sys.stdin.isatty():
            raw = getpass.getpass("รหัสผ่านชั่วคราว: ")
        else:
            raw = sys.stdin.read(MAX_SECRET_BYTES + 1)
            if len(raw) > MAX_SECRET_BYTES:
                raise CommandError("ข้อมูลรหัสผ่านจาก stdin มีขนาดเกินขอบเขตที่อนุญาต")
        return _clean_secret(raw)

    def handle(self, *args, **options):
        username = options["username"]
        operator_username = options["operator"]
        target = self._resolve_user(username, role="บัญชีเป้าหมาย")
        operator = self._resolve_user(operator_username, role="operator")

        if not operator.is_active or not operator.is_superuser:
            raise CommandError("operator ต้องเป็นบัญชี superuser ที่เปิดใช้งาน")
        if not target.is_active:
            raise CommandError("บัญชีเป้าหมายปิดใช้งานอยู่ จึงไม่รีเซ็ตรหัสผ่าน")

        if options.get("dry_run"):
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN PASS target={target.username} operator={operator.username} "
                    "active_target=true active_superuser_operator=true"
                )
            )
            return

        expected_confirmation = f"RESET:{target.username}"
        if options.get("confirm") != expected_confirmation:
            raise CommandError(f"ต้องระบุ --confirm {expected_confirmation} ให้ตรงกัน")

        raw_password = self._read_password(options)
        try:
            updated, audit_row = reset_password_by_superuser(
                operator=operator,
                target=target,
                raw_password=raw_password,
            )
        except PermissionDenied as exc:
            raise CommandError(str(exc)) from exc
        except ValidationError as exc:
            messages = getattr(exc, "messages", None) or [str(exc)]
            raise CommandError("รหัสผ่านไม่ผ่านนโยบาย: " + "; ".join(messages)) from exc
        finally:
            raw_password = None

        self.stdout.write(
            self.style.SUCCESS(
                f"รีเซ็ตรหัสผ่าน {updated.username} สำเร็จ; "
                f"must_change_password=true; audit_id={audit_row.pk}"
            )
        )

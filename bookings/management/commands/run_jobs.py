from django.core.management.base import BaseCommand
from django.utils import timezone

from approvals.services import run_scheduled_jobs


class Command(BaseCommand):
    help = "หมดอายุคำขอ เปิดสิทธิ์สำรอง ปิดงานรับทราบ และบันทึกใช้งานแล้วอัตโนมัติ"

    def handle(self, *args, **options):
        counts = run_scheduled_jobs(timezone.now())
        self.stdout.write(
            self.style.SUCCESS(
                f"เสร็จ — หมดอายุ {counts['expired']} คำขอ · เปิดสิทธิ์สำรอง {counts['escalated']} คำขอ · "
                f"amendment หมดอายุ {counts['amendment_expired']} · amendment เกิน SLA {counts['amendment_escalated']} · "
                f"ถือว่ารับทราบบังคับย้าย {counts['deemed_acknowledged']} · ใช้งานแล้วอัตโนมัติ {counts['usage_used']}"
            )
        )

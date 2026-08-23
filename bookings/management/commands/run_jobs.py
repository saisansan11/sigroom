from django.core.management.base import BaseCommand
from django.utils import timezone

from approvals.services import run_scheduled_jobs


class Command(BaseCommand):
    help = "หมดอายุคำขอและเปิดสิทธิ์ผู้อนุมัติสำรองสำหรับคำขอที่เกิน SLA"

    def handle(self, *args, **options):
        counts = run_scheduled_jobs(timezone.now())
        self.stdout.write(
            self.style.SUCCESS(
                f"เสร็จ — หมดอายุ {counts['expired']} คำขอ · เปิดสิทธิ์สำรอง {counts['escalated']} คำขอ"
            )
        )

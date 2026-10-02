"""ไฟล์ปฏิทิน .ics ของการจองหนึ่งรายการ (ปุ่ม "เพิ่มลงปฏิทิน")

รูปแบบตาม RFC 5545: เวลาเป็น UTC (ลงท้าย Z) ปฏิทินในมือถือแปลงเป็นเวลาไทยเอง,
บรรทัดยาวพับที่ 75 ไบต์โดยไม่ตัดกลางตัวอักษรไทย (UTF-8 ตัวละ 3 ไบต์), ขึ้นบรรทัดด้วย CRLF
"""
from datetime import datetime, timezone as dt_timezone

from django.utils import timezone

from .models import Booking

ICS_STATUS = {
    Booking.RequestStatus.APPROVED: "CONFIRMED",
    Booking.RequestStatus.PENDING: "TENTATIVE",
}


def _utc(value: datetime) -> str:
    return value.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """พับบรรทัดที่ยาวเกิน 75 ไบต์ (บรรทัดต่อขึ้นต้นด้วยช่องว่าง 1 ตัว)"""
    parts, current, size = [], "", 0
    for char in line:
        width = len(char.encode("utf-8"))
        limit = 75 if not parts else 74
        if size + width > limit:
            parts.append(current)
            current, size = "", 0
        current += char
        size += width
    parts.append(current)
    return "\r\n ".join(parts)


def booking_ics(booking: Booking, detail_url: str = "", now: datetime | None = None) -> str:
    room = booking.room
    location = " ".join(part for part in (room.code, room.name, room.building) if part)
    status_label = booking.get_request_status_display()
    description = f"ผู้รับผิดชอบ {booking.responsible_name} โทร {booking.responsible_phone}\nสถานะ: {status_label}"
    if detail_url:
        description += f"\nรายละเอียด: {detail_url}"
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SIGROOM//Signal School Room Booking//TH",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{booking.pk}@sigroom",
        f"DTSTAMP:{_utc(now or timezone.now())}",
        f"DTSTART:{_utc(booking.start_at)}",
        f"DTEND:{_utc(booking.end_at)}",
        f"SUMMARY:{_escape(f'{booking.title} ({room.code})')}",
        f"LOCATION:{_escape(location)}",
        f"DESCRIPTION:{_escape(description)}",
        f"STATUS:{ICS_STATUS.get(booking.request_status, 'CANCELLED')}",
        f"SEQUENCE:{max(booking.revision - 1, 0)}",
    ]
    if detail_url:
        lines.append(f"URL:{detail_url}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"

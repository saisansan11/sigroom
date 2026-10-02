from django import template
from django.utils import timezone

register = template.Library()

THAI_MONTHS_SHORT = ("", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")


@register.filter
def thai_date(value):
    if not value:
        return "—"
    if isinstance(value, str):
        # ค่าจากฟอร์มที่ผู้ใช้พิมพ์เป็น วัน/เดือน/ปี พ.ศ. อยู่แล้ว
        return value
    if hasattr(value, "hour"):
        value = timezone.localtime(value).date()
    return f"{value.day} {THAI_MONTHS_SHORT[value.month]} {value.year + 543}"


@register.filter
def thai_datetime(value):
    if not value:
        return "—"
    value = timezone.localtime(value)
    return f"{value.day} {THAI_MONTHS_SHORT[value.month]} {value.year + 543} {value:%H:%M} น."


THAI_MONTHS_FULL = (
    "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
)
THAI_WEEKDAYS = ("จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์")
_THAI_DIGITS = str.maketrans("0123456789", "๐๑๒๓๔๕๖๗๘๙")


@register.filter
def thai_digits(value):
    """แปลงเลขอารบิกเป็นเลขไทย — ใช้เฉพาะวันที่แบบเต็ม/หัวกระดาษ (สเปกธีม A)"""
    return str(value).translate(_THAI_DIGITS)


@register.filter
def thai_date_full(value):
    """วันที่แบบหนังสือราชการ เช่น "วันพฤหัสบดีที่ ๒ ตุลาคม พ.ศ. ๒๕๖๙" (เลขไทย)"""
    if not value:
        return "—"
    if hasattr(value, "hour"):
        value = timezone.localtime(value).date()
    text = f"วัน{THAI_WEEKDAYS[value.weekday()]}ที่ {value.day} {THAI_MONTHS_FULL[value.month]} พ.ศ. {value.year + 543}"
    return thai_digits(text)

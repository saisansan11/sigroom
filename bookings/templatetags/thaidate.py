from django import template
from django.utils import timezone

register = template.Library()

THAI_MONTHS_SHORT = ("", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.")


@register.filter
def thai_date(value):
    if not value:
        return "—"
    if hasattr(value, "hour"):
        value = timezone.localtime(value).date()
    return f"{value.day} {THAI_MONTHS_SHORT[value.month]} {value.year + 543}"


@register.filter
def thai_datetime(value):
    if not value:
        return "—"
    value = timezone.localtime(value)
    return f"{value.day} {THAI_MONTHS_SHORT[value.month]} {value.year + 543} {value:%H:%M} น."

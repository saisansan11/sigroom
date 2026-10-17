from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from bookings.models import Booking

from .services import (
    SERVICE_ROOM_CATEGORIES,
    can_manage_room_categories,
    can_manage_usage,
    recent_bookings_for,
    set_usage_status,
    usage_change_is_open,
)


@login_required
def usage_list(request):
    if not can_manage_usage(request.user):
        raise PermissionDenied

    service = (request.GET.get("service") or "").strip()
    categories = SERVICE_ROOM_CATEGORIES.get(service) if service else None
    if service and categories is None:
        raise PermissionDenied("ไม่พบขอบเขตงานผู้ดูแลที่ร้องขอ")
    if categories and not can_manage_room_categories(request.user, categories):
        raise PermissionDenied("บัญชีนี้ไม่ได้รับมอบหมายให้ดูแลห้องในส่วนนี้")

    bookings = list(recent_bookings_for(request.user, categories=categories))
    for booking in bookings:
        booking.usage_change_open = usage_change_is_open(booking)

    labels = {
        "online": ("ห้องสอนออนไลน์", "เฉพาะห้องสอนออนไลน์ที่ท่านได้รับมอบหมาย"),
        "learning": ("ห้องเรียน / ห้องประชุม", "เฉพาะห้องเรียน ห้องปฏิบัติ และห้องประชุมที่ท่านได้รับมอบหมาย"),
    }
    title, scope_note = labels.get(service, ("ห้องที่ฉันดูแล", "แสดงเฉพาะห้องที่ท่านได้รับมอบหมาย"))
    return render(
        request,
        "usage/list.html",
        {
            "bookings": bookings,
            "service": service,
            "service_title": title,
            "service_scope_note": scope_note,
        },
    )


@login_required
@require_POST
def usage_update(request, id):
    booking = get_object_or_404(Booking.objects.select_related("room", "requester"), pk=id)
    service = (request.GET.get("service") or "").strip()
    categories = SERVICE_ROOM_CATEGORIES.get(service) if service else None
    if service and categories is None:
        raise PermissionDenied("ไม่พบขอบเขตงานผู้ดูแลที่ร้องขอ")
    if categories and booking.room.room_category not in categories:
        raise PermissionDenied("รายการนี้อยู่นอกส่วนงานที่กำลังดูแล")
    try:
        set_usage_status(booking, request.user, request.POST.get("status", ""))
    except PermissionError as exc:
        raise PermissionDenied(str(exc))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "บันทึกสถานะการใช้งานแล้ว")

    if service in SERVICE_ROOM_CATEGORIES:
        return redirect(f"{reverse('usage:list')}?service={service}")
    return redirect("usage:list")

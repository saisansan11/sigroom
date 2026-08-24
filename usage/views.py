from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from bookings.models import Booking

from .services import can_manage_usage, recent_bookings_for, set_usage_status, usage_change_is_open


@login_required
def usage_list(request):
    if not can_manage_usage(request.user):
        raise PermissionDenied
    bookings = list(recent_bookings_for(request.user))
    for booking in bookings:
        booking.usage_change_open = usage_change_is_open(booking)
    return render(request, "usage/list.html", {"bookings": bookings})


@login_required
@require_POST
def usage_update(request, id):
    booking = get_object_or_404(Booking.objects.select_related("room", "requester"), pk=id)
    try:
        set_usage_status(booking, request.user, request.POST.get("status", ""))
    except PermissionError as exc:
        raise PermissionDenied(str(exc))
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "บันทึกสถานะการใช้งานแล้ว")
    return redirect("usage:list")


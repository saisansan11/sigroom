from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from bookings.models import Booking, BookingSeries
from resources.models import ResourceApprover

from .forms import DelegationForm
from .models import ApproverDelegation
from .services import (
    approve_booking,
    decide_series,
    has_approval_role,
    pending_for,
    recent_rejection_reasons,
    reject_booking,
)


def _return_to(request, default="approvals:queue"):
    target = request.POST.get("next", "")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(target)
    return redirect(default)


@login_required
def queue(request):
    now = timezone.now()
    bookings = pending_for(request.user, now)
    if not bookings and not has_approval_role(request.user, now):
        raise PermissionDenied("คุณไม่มีหน้าที่อนุมัติห้อง")
    return render(
        request,
        "approvals/queue.html",
        {
            "bookings": bookings,
            "rejection_reasons": recent_rejection_reasons(request.user),
            "can_delegate": ResourceApprover.objects.filter(user=request.user, is_primary=True).exists(),
        },
    )


@login_required
@require_POST
def approve(request, id):
    booking = get_object_or_404(Booking, pk=id)
    if booking.series_id:
        messages.error(request, "กรุณาพิจารณาชุดการจองทั้งชุดจากการ์ดชุด")
        return _return_to(request)
    try:
        approve_booking(booking, request.user)
    except (PermissionError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "อนุมัติคำขอแล้ว")
    return _return_to(request)


@login_required
@require_POST
def reject(request, id):
    booking = get_object_or_404(Booking, pk=id)
    if booking.series_id:
        messages.error(request, "กรุณาพิจารณาชุดการจองทั้งชุดจากการ์ดชุด")
        return _return_to(request)
    try:
        reject_booking(booking, request.user, request.POST.get("reason", ""))
    except (PermissionError, ValueError, ValidationError) as exc:
        text = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        messages.error(request, text)
    else:
        messages.success(request, "ปฏิเสธคำขอและคืนช่วงเวลาแล้ว")
    return _return_to(request)


@login_required
@require_POST
def series_decide(request, id):
    series = get_object_or_404(BookingSeries, pk=id)
    try:
        result = decide_series(
            series,
            request.user,
            request.POST.get("action", ""),
            request.POST.getlist("excluded"),
            request.POST.get("reason_excluded", ""),
            request.POST.get("reason_reject", ""),
        )
    except (PermissionError, ValueError, ValidationError) as exc:
        text = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        messages.error(request, text)
    else:
        messages.success(request, f"พิจารณาชุดแล้ว: อนุมัติ {result['approved']} · ปฏิเสธ {result['rejected']} ครั้ง")
    return _return_to(request)


@login_required
def delegation(request):
    if not request.user.approver_of.filter(is_primary=True).exists():
        raise PermissionDenied("เฉพาะผู้อนุมัติหลักเท่านั้นที่มอบหมายผู้รักษาการได้")
    form = DelegationForm(request.POST or None, delegator=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except (PermissionError, ValidationError) as exc:
            text = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
            form.add_error(None, text)
        else:
            messages.success(request, "บันทึกผู้รักษาการแล้ว")
            return redirect("approvals:delegation")
    items = request.user.delegations_given.select_related("delegate").all()
    today = timezone.localdate()
    for item in items:
        if item.end_date < today:
            item.display_status = "สิ้นสุด"
        elif item.start_date > today:
            item.display_status = "รอถึงวัน"
        else:
            item.display_status = "กำลังใช้"
    return render(request, "approvals/delegation.html", {"form": form, "delegations": items, "today": today})


@login_required
@require_POST
def delegation_delete(request, id):
    item = get_object_or_404(ApproverDelegation, pk=id, delegator=request.user)
    if item.end_date < timezone.localdate():
        messages.error(request, "รายการนี้สิ้นสุดแล้วและยกเลิกไม่ได้")
    else:
        item.delete()
        messages.success(request, "ยกเลิกการมอบหมายแล้ว")
    return redirect("approvals:delegation")

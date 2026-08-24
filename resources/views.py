from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ResourceOutageForm
from .models import Resource, ResourceOutage
from .services import (
    affected_bookings,
    can_manage_outage,
    create_outage,
    end_outage_early,
    recent_outage_reasons,
)


@login_required
def outage(request, code):
    resource = get_object_or_404(Resource, code=code, resource_type=Resource.Type.ROOM)
    if not can_manage_outage(request.user, resource):
        raise PermissionDenied("เฉพาะเจ้าหน้าที่ดูแลห้องหรือผู้ดูแลระบบเท่านั้นที่ตั้งงดใช้ได้")
    form = ResourceOutageForm(request.POST or None)
    affected = None
    if request.method == "POST" and form.is_valid():
        start = form.cleaned_data["start_at"]
        end = form.cleaned_data["end_at"]
        if request.POST.get("action") == "confirm":
            try:
                _, affected_items = create_outage(
                    resource, request.user, start, end, form.cleaned_data["reason"]
                )
            except (PermissionError, ValidationError) as exc:
                text = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                form.add_error(None, text)
            else:
                messages.success(request, f"ตั้งงดใช้ห้องแล้ว · กระทบ {len(affected_items)} รายการ")
                return redirect("resources:outage", code=resource.code)
        else:
            affected = list(affected_bookings(resource, start, end))
    outages = resource.outages.select_related("created_by").all()
    return render(
        request,
        "resources/outage.html",
        {
            "resource": resource,
            "form": form,
            "affected": affected,
            "outages": outages,
            "reasons": recent_outage_reasons(request.user),
        },
    )


@login_required
@require_POST
def outage_end(request, id):
    item = get_object_or_404(ResourceOutage.objects.select_related("resource"), pk=id)
    try:
        restored = end_outage_early(item, request.user)
    except (PermissionError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"สิ้นสุดช่วงงดใช้แล้ว · คืนสถานะ {len(restored)} รายการ")
    return redirect("resources:outage", code=item.resource.code)

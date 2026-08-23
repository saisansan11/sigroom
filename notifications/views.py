from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification
from .services import mark_read


@login_required
def notification_list(request):
    items = Notification.objects.filter(user=request.user)[:50]
    return render(request, "notifications/list.html", {"notifications": items})


@login_required
@require_POST
def read_all(request):
    mark_read(request.user, all=True)
    messages.success(request, "ทำเครื่องหมายว่าอ่านทั้งหมดแล้ว")
    return redirect("notifications:list")


@login_required
def open_notification(request, id):
    item = get_object_or_404(Notification, pk=id, user=request.user)
    mark_read(request.user, item.pk)
    if item.url.startswith("/") and not item.url.startswith("//"):
        return redirect(item.url)
    return redirect("notifications:list")

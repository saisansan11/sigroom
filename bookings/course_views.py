from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .course_catalog import (
    can_manage_course_catalog,
    course_run_status,
    create_next_course_run,
    next_run_defaults,
)
from .models import Course


@login_required
def course_catalog_manage(request):
    """Friendly shared course/run workspace for non-technical staff."""
    if not can_manage_course_catalog(request.user):
        raise PermissionDenied("คุณไม่มีสิทธิ์จัดการหลักสูตรและรุ่น")

    if request.method == "POST":
        course = get_object_or_404(Course, pk=request.POST.get("course_id"), is_active=True)
        try:
            start_date = date.fromisoformat(request.POST.get("start_date", ""))
            end_date = date.fromisoformat(request.POST.get("end_date", ""))
            run = create_next_course_run(
                course=course,
                start_date=start_date,
                end_date=end_date,
                actor=request.user,
            )
        except (TypeError, ValueError, ValidationError, PermissionDenied) as exc:
            messages.error(request, f"เปิดรุ่นใหม่ไม่สำเร็จ: {exc}")
        else:
            messages.success(request, f"เปิด {run.display_name} เรียบร้อยแล้ว")
        return redirect("bookings:course_catalog_manage")

    courses = list(Course.objects.filter(is_active=True).prefetch_related("runs").order_by("name"))
    for course in courses:
        runs = sorted(course.runs.all(), key=lambda item: (item.start_date, item.run_number), reverse=True)
        course.recent_runs = runs[:4]
        course.next_run_number, course.next_year_code = next_run_defaults(course)
        for run in course.recent_runs:
            run.status_key, run.status_label = course_run_status(run)

    return render(
        request,
        "bookings/course_catalog_manage.html",
        {"courses": courses},
    )

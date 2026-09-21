"""Shared course catalog and course-run helpers for SIGROOM.

A course name is stored once. Repeated deliveries are represented by CourseRun so
staff normally create only the next run and its dates instead of retyping the full
course title every year.
"""
from __future__ import annotations

import re
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from audit.services import audit

from .models import Course, CourseRun


COURSE_TITLE_RE = re.compile(r"^(?P<name>.+?)\s+รุ่นที่\s+(?P<run>\d+)(?:/(?P<year>\d+))?$")


def split_course_title(title: str) -> tuple[str, int, str]:
    """Split legacy full title into stable course name + run metadata."""
    value = (title or "").strip()
    match = COURSE_TITLE_RE.fullmatch(value)
    if not match:
        raise ValidationError(f"รูปแบบชื่อหลักสูตรไม่รองรับ: {value}")
    return match.group("name").strip(), int(match.group("run")), match.group("year") or ""


def course_code_from_run_slug(slug: str, run_number: int, year_code: str = "") -> str:
    suffix = f"-{run_number}"
    if year_code:
        suffix += f"-{year_code}"
    if not slug.endswith(suffix):
        raise ValidationError(f"รหัสรุ่น {slug} ไม่สอดคล้องกับรุ่นที่ {run_number}")
    code = slug[: -len(suffix)].strip("-")
    if not code:
        raise ValidationError(f"ไม่สามารถหารหัสหลักสูตรแม่จาก {slug}")
    return code


def can_manage_course_catalog(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(
        getattr(user, "is_superuser", False)
        or user.has_perm("bookings.add_courserun")
        or user.has_perm("bookings.change_courserun")
        or user.has_perm("bookings.add_courselodgingcohort")
    )


def course_run_status(run: CourseRun, today: date | None = None) -> tuple[str, str]:
    today = today or timezone.localdate()
    if not run.is_active:
        return "closed", "ปิดใช้งาน"
    if run.end_date < today:
        return "ended", "จบแล้ว"
    if run.start_date > today:
        return "upcoming", "ยังไม่เริ่ม"
    return "active", "กำลังเปิดเรียน"


def selectable_course_runs():
    """Runs teachers may select: active and not already ended."""
    return (
        CourseRun.objects.select_related("course")
        .filter(course__is_active=True, is_active=True, end_date__gte=timezone.localdate())
        .order_by("start_date", "course__name", "run_number")
    )


def next_run_defaults(course: Course) -> tuple[int, str]:
    latest = course.runs.order_by("-run_number", "-start_date", "-pk").first()
    if latest is None:
        return 1, ""
    next_number = latest.run_number + 1
    next_year = ""
    if course.include_year_in_label:
        numeric_years = [
            int(value)
            for value in course.runs.exclude(year_code="").values_list("year_code", flat=True)
            if str(value).isdigit()
        ]
        if numeric_years:
            latest_year = max(numeric_years)
            width = max(2, len(str(latest.year_code or latest_year)))
            next_year = str(latest_year + 1).zfill(width)
    return next_number, next_year


@transaction.atomic
def create_next_course_run(*, course: Course, start_date: date, end_date: date, actor) -> CourseRun:
    if not can_manage_course_catalog(actor):
        raise PermissionDenied("คุณไม่มีสิทธิ์เปิดรุ่นหลักสูตร")
    if end_date < start_date:
        raise ValidationError("วันที่สิ้นสุดต้องไม่ก่อนวันที่เริ่ม")

    locked_course = Course.objects.select_for_update().get(pk=course.pk)
    run_number, year_code = next_run_defaults(locked_course)
    suffix = f"-{run_number}"
    if year_code:
        suffix += f"-{year_code}"
    slug = f"{locked_course.code}{suffix}"
    try:
        run = CourseRun.objects.create(
            course=locked_course,
            slug=slug,
            run_number=run_number,
            year_code=year_code,
            start_date=start_date,
            end_date=end_date,
            is_active=True,
        )
    except IntegrityError as exc:
        raise ValidationError("มีรุ่นนี้อยู่แล้ว กรุณารีเฟรชหน้าแล้วตรวจสอบอีกครั้ง") from exc
    audit(
        actor,
        "bookings.courserun",
        run.pk,
        "course_run_created",
        after={
            "course": str(locked_course.pk),
            "slug": run.slug,
            "run_number": run.run_number,
            "year_code": run.year_code,
            "start_date": run.start_date.isoformat(),
            "end_date": run.end_date.isoformat(),
        },
    )
    return run


def ensure_course_run(*, title: str, slug: str, start_date: date, end_date: date) -> CourseRun:
    """Idempotently publish one known legacy row into the shared catalog."""
    name, run_number, year_code = split_course_title(title)
    course_code = course_code_from_run_slug(slug, run_number, year_code)
    course, _ = Course.objects.get_or_create(
        code=course_code,
        defaults={
            "name": name,
            "include_year_in_label": bool(year_code),
            "is_active": True,
        },
    )
    if course.name != name:
        raise ValidationError(f"รหัสหลักสูตร {course_code} มีชื่อไม่ตรงกับข้อมูลเดิม")
    if bool(year_code) and not course.include_year_in_label:
        course.include_year_in_label = True
        course.save(update_fields=["include_year_in_label"])

    run, created = CourseRun.objects.get_or_create(
        slug=slug,
        defaults={
            "course": course,
            "run_number": run_number,
            "year_code": year_code,
            "start_date": start_date,
            "end_date": end_date,
            "is_active": True,
        },
    )
    if not created:
        expected = (course.pk, run_number, year_code)
        actual = (run.course_id, run.run_number, run.year_code)
        if actual != expected:
            raise ValidationError(f"รหัสรุ่น {slug} ชนกับข้อมูลหลักสูตรอื่น")
        updates = []
        if run.start_date != start_date:
            run.start_date = start_date
            updates.append("start_date")
        if run.end_date != end_date:
            run.end_date = end_date
            updates.append("end_date")
        if updates:
            run.save(update_fields=updates)
    return run

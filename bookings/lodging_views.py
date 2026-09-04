import csv
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from resources.models import Resource
from .lodging_models import CourseLodgingCohort, CourseStudentLodging
from .lodging_services import (
    can_create_cohort,
    can_manage_cohort,
    generate_cohort_qr_svg,
    generate_line_share_url,
    get_canonical_public_url,
    normalize_phone,
    update_cohort_allocation,
)


def _masked_name(full_name: str) -> str:
    return " ".join(
        f"{part[:1]}***" if part else part
        for part in (full_name or "").split()
    )


def _masked_student_label(student: CourseStudentLodging) -> str:
    return f"{student.rank} {_masked_name(student.full_name)}".strip()


def lodging_portal(request, slug):
    """หน้าจอเลือกห้องพักสำหรับนักเรียนหลักสูตร (ไม่ต้องเข้าสู่ระบบ สะดวกบนมือถือ)"""
    cohort = get_object_or_404(
        CourseLodgingCohort.objects.prefetch_related("rooms"),
        slug=slug,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    students = CourseStudentLodging.objects.filter(cohort=cohort).select_related("room")
    students_by_room_bed = {
        (s.room_id, s.bed_number): s for s in students
    }

    rooms_data = []
    total_slots = 0
    occupied_slots = 0

    for room in cohort.rooms.all().order_by("building", "floor", "code"):
        beds = []
        beds_count = cohort.beds_per_room
        room_occupied = 0
        for b_num in range(1, beds_count + 1):
            total_slots += 1
            student = students_by_room_bed.get((room.id, b_num))
            if student:
                occupied_slots += 1
                room_occupied += 1
                beds.append({
                    "number": b_num,
                    "is_occupied": True,
                    "student": None,
                    "occupant_label": "มีผู้จองแล้ว",
                })
            else:
                beds.append({
                    "number": b_num,
                    "is_occupied": False,
                    "student": None,
                })
        rooms_data.append({
            "room": room,
            "beds": beds,
            "occupied_count": room_occupied,
            "beds_count": beds_count,
            "is_full": room_occupied >= beds_count,
        })

    context = {
        "cohort": cohort,
        "rooms_data": rooms_data,
        "total_slots": total_slots,
        "occupied_slots": occupied_slots,
        "free_slots": max(0, total_slots - occupied_slots),
    }
    return render(request, "lodging/student_portal.html", context)


@require_POST
def lodging_book_bed(request, slug):
    """ส่งข้อมูลจองเตียงในห้องพัก (atomic transaction กันชนเตียงเดียวกัน)"""
    cohort = get_object_or_404(
        CourseLodgingCohort,
        slug=slug,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    room_id = request.POST.get("room_id")
    bed_number_raw = request.POST.get("bed_number")
    rank = request.POST.get("rank", "").strip()
    full_name = request.POST.get("full_name", "").strip()
    origin_unit = request.POST.get("origin_unit", "").strip()
    phone = normalize_phone(request.POST.get("phone", ""))
    note = request.POST.get("note", "").strip()

    if not all([room_id, bed_number_raw, rank, full_name, origin_unit, phone]):
        messages.error(request, "กรุณากรอกข้อมูลให้ครบทุกช่อง (ยศ, ชื่อ-สกุล, สังกัด, เบอร์โทร)")
        return redirect("bookings:lodging_portal", slug=slug)

    try:
        bed_number = int(bed_number_raw)
        if not (1 <= bed_number <= cohort.beds_per_room):
            raise ValueError
    except (TypeError, ValueError):
        messages.error(request, "หมายเลขเตียงไม่ถูกต้อง")
        return redirect("bookings:lodging_portal", slug=slug)

    try:
        with transaction.atomic():
            cohort = CourseLodgingCohort.objects.select_for_update().get(pk=cohort.pk)
            room = get_object_or_404(cohort.rooms.all(), pk=room_id)
            Resource.objects.select_for_update().get(pk=room.pk)
            # ตรวจสอบว่าเตียงนี้ในห้องนี้มีผู้จองแล้วหรือไม่
            existing_bed = CourseStudentLodging.objects.filter(
                cohort=cohort, room=room, bed_number=bed_number
            ).exists()
            if existing_bed:
                messages.error(request, f"ขออภัย ห้อง {room.code} เตียง {bed_number} มีเพื่อนร่วมรุ่นเพิ่งจองไปแล้ว กรุณาเลือกเตียงอื่น")
                return redirect("bookings:lodging_portal", slug=slug)

            # ตรวจสอบซ้ำโดยไม่เปิดเผยห้อง/เตียงเดิมต่อผู้ส่งคำขอ
            if CourseStudentLodging.objects.filter(cohort=cohort, phone=phone).exists():
                messages.warning(request, "เบอร์โทรศัพท์นี้ลงทะเบียนในรอบนี้แล้ว กรุณาตรวจสอบข้อมูลเดิมหรือติดต่อผู้กำกับหลักสูตร")
                return redirect("bookings:lodging_portal", slug=slug)

            student = CourseStudentLodging.objects.create(
                cohort=cohort,
                room=room,
                bed_number=bed_number,
                rank=rank,
                full_name=full_name,
                origin_unit=origin_unit,
                phone=phone,
                note=note,
            )
    except (IntegrityError, ValidationError):
        messages.error(request, "เกิดข้อผิดพลาดในการบันทึก หรือเตียงนี้มีผู้จองแล้ว กรุณาลองใหม่อีกครั้ง")
        return redirect("bookings:lodging_portal", slug=slug)

    messages.success(request, f"ลงทะเบียนจองห้อง {room.code} เตียง {bed_number} สำเร็จ!")
    return redirect("bookings:lodging_pass", slug=slug, student_id=student.id)


def lodging_pass(request, slug, student_id):
    """บัตรยืนยันการเข้าพักสำหรับนักเรียนแคปหน้าจอไว้เป็นหลักฐาน"""
    cohort = get_object_or_404(CourseLodgingCohort, slug=slug)
    student = get_object_or_404(CourseStudentLodging.objects.select_related("room", "cohort"), pk=student_id, cohort=cohort)
    roommates = CourseStudentLodging.objects.filter(
        cohort=cohort, room=student.room
    ).exclude(pk=student.pk).order_by("bed_number")
    for roommate in roommates:
        roommate.masked_label = _masked_student_label(roommate)

    response = render(
        request,
        "lodging/student_pass.html",
        {
            "cohort": cohort,
            "student": student,
            "roommates": roommates,
        },
    )
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def lodging_index(request):
    """หน้ารวมลิงก์รอบที่พักที่กำลังเปิดรับจองสำหรับนักเรียน"""
    cohorts = CourseLodgingCohort.objects.filter(
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    ).prefetch_related("rooms").order_by("check_in_date", "title")
    return render(request, "lodging/lodging_index.html", {"cohorts": cohorts})


@login_required
def lodging_manage(request):
    """หน้าสำหรับผู้กำกับหลักสูตร: ดูและสร้างรอบการจองที่พัก"""
    if not can_create_cohort(request.user):
        raise PermissionDenied("คุณไม่มีสิทธิ์จัดการรอบที่พัก")
    cohorts = CourseLodgingCohort.objects.all().prefetch_related("rooms", "students")
    if not (request.user.is_superuser or request.user.is_staff):
        cohorts = cohorts.filter(supervisor=request.user)
    lodging_rooms = Resource.objects.filter(
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        status=Resource.Status.ACTIVE,
    ).order_by("building", "code")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        slug = request.POST.get("slug", "").strip().lower()
        check_in_raw = request.POST.get("check_in_date")
        check_out_raw = request.POST.get("check_out_date")
        beds_per_room_raw = request.POST.get("beds_per_room", "4")
        room_ids = request.POST.getlist("rooms")
        note = request.POST.get("note", "").strip()

        if not all([title, slug, check_in_raw, check_out_raw, room_ids]):
            messages.error(request, "กรุณากรอกข้อมูลและเลือกห้องพักให้ครบถ้วน")
        else:
            try:
                beds_per_room = int(beds_per_room_raw)
                check_in_date = datetime.strptime(check_in_raw, "%Y-%m-%d").date()
                check_out_date = datetime.strptime(check_out_raw, "%Y-%m-%d").date()
                if CourseLodgingCohort.objects.filter(slug=slug).exists():
                    messages.error(request, f"รหัสลิงก์ '{slug}' มีอยู่ในระบบแล้ว กรุณาตั้งรหัสอื่น")
                else:
                    cohort = CourseLodgingCohort(
                        title=title,
                        slug=slug,
                        supervisor=request.user,
                        unit=request.user.unit,
                        check_in_date=check_in_date,
                        check_out_date=check_out_date,
                        beds_per_room=beds_per_room,
                        note=note,
                    )
                    update_cohort_allocation(
                        cohort=cohort,
                        rooms=Resource.objects.filter(
                            id__in=room_ids,
                            resource_type=Resource.Type.ROOM,
                            room_category=Resource.Category.LODGING,
                            status=Resource.Status.ACTIVE,
                        ),
                        check_in_date=check_in_date,
                        check_out_date=check_out_date,
                        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
                        is_active=True,
                        beds_per_room=beds_per_room,
                        supervisor=request.user,
                        title=title,
                        note=note,
                        actor=request.user,
                    )
                    messages.success(request, f"สร้างรอบจอง '{title}' เรียบร้อยแล้ว สามารถคัดลอกลิงก์ส่งให้นักเรียนได้ทันที")
                    return redirect("bookings:lodging_cohort_detail", slug=cohort.slug)
            except (ValueError, ValidationError, IntegrityError, PermissionDenied) as e:
                messages.error(request, f"เกิดข้อผิดพลาด: {e}")

    return render(
        request,
        "lodging/manage_list.html",
        {
            "cohorts": cohorts,
            "lodging_rooms": lodging_rooms,
        },
    )


@login_required
def lodging_cohort_detail(request, slug):
    """ดูรายละเอียดและรายชื่อนักเรียนในรอบหลักสูตร"""
    cohort = get_object_or_404(CourseLodgingCohort.objects.prefetch_related("rooms"), slug=slug)
    if not can_manage_cohort(request.user, cohort):
        raise PermissionDenied("คุณไม่มีสิทธิ์ดูข้อมูลผู้เข้าพักของรุ่นนี้")
    students = CourseStudentLodging.objects.filter(cohort=cohort).select_related("room").order_by("room__code", "bed_number")

    students_by_room = {}
    for s in students:
        students_by_room.setdefault(s.room_id, []).append(s)

    rooms_summary = []
    for room in cohort.rooms.all().order_by("code"):
        room_students = students_by_room.get(room.id, [])
        rooms_summary.append({
            "room": room,
            "students": room_students,
            "count": len(room_students),
            "free": cohort.beds_per_room - len(room_students),
        })

    share_path = reverse("bookings:lodging_portal", args=[cohort.slug])
    share_url = get_canonical_public_url(request, share_path)

    return render(
        request,
        "lodging/cohort_detail.html",
        {
            "cohort": cohort,
            "students": students,
            "rooms_summary": rooms_summary,
            "share_url": share_url,
            "line_share_url": generate_line_share_url(cohort.title, share_url),
            "qr_url": reverse("bookings:lodging_cohort_qr_svg", args=[cohort.slug]),
        },
    )


@login_required
def lodging_cohort_edit(request, slug):
    cohort = get_object_or_404(CourseLodgingCohort, slug=slug)
    if not can_manage_cohort(request.user, cohort):
        raise PermissionDenied("คุณไม่มีสิทธิ์แก้ไขรอบที่พักนี้")
    lodging_rooms = Resource.objects.filter(
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        status=Resource.Status.ACTIVE,
    ).order_by("building", "code")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        check_in_raw = request.POST.get("check_in_date", "")
        check_out_raw = request.POST.get("check_out_date", "")
        beds_per_room_raw = request.POST.get("beds_per_room", "")
        room_ids = request.POST.getlist("rooms")
        allocation_status = request.POST.get(
            "allocation_status", CourseLodgingCohort.AllocationStatus.RELEASED
        )
        is_active = bool(request.POST.get("is_active"))
        note = request.POST.get("note", "").strip()
        force_release = bool(request.POST.get("force_release"))
        release_reason = request.POST.get("release_reason", "").strip()
        try:
            check_in_date = datetime.strptime(check_in_raw, "%Y-%m-%d").date()
            check_out_date = datetime.strptime(check_out_raw, "%Y-%m-%d").date()
            beds_per_room = int(beds_per_room_raw)
            updated = update_cohort_allocation(
                cohort=cohort,
                rooms=lodging_rooms.filter(pk__in=room_ids),
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                allocation_status=allocation_status,
                is_active=is_active,
                beds_per_room=beds_per_room,
                supervisor=cohort.supervisor,
                title=title,
                note=note,
                actor=request.user,
                force_release=force_release,
                release_reason=release_reason,
            )
            messages.success(request, f"บันทึกการเปลี่ยนแปลงรอบ '{updated.title}' แล้ว")
            return redirect("bookings:lodging_cohort_detail", slug=updated.slug)
        except (ValueError, ValidationError, IntegrityError, PermissionDenied) as exc:
            messages.error(request, f"ไม่สามารถบันทึกการเปลี่ยนแปลงได้: {exc}")

    return render(
        request,
        "lodging/cohort_edit.html",
        {
            "cohort": cohort,
            "lodging_rooms": lodging_rooms,
            "status_choices": CourseLodgingCohort.AllocationStatus.choices,
        },
    )


@login_required
def lodging_cohort_qr_svg(request, slug):
    cohort = get_object_or_404(CourseLodgingCohort, slug=slug)
    if not can_manage_cohort(request.user, cohort):
        raise PermissionDenied("คุณไม่มีสิทธิ์สร้าง QR ของรุ่นนี้")
    path = reverse("bookings:lodging_portal", args=[cohort.slug])
    url = get_canonical_public_url(request, path)
    response = HttpResponse(generate_cohort_qr_svg(url), content_type="image/svg+xml")
    response["Content-Disposition"] = f'inline; filename="lodging_{cohort.slug}.svg"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def lodging_cohort_export_csv(request, slug):
    """ส่งออกรายชื่อผู้พักในหลักสูตรเป็นไฟล์ CSV (UTF-8 BOM สำหรับ Excel)"""
    cohort = get_object_or_404(CourseLodgingCohort, slug=slug)
    if not can_manage_cohort(request.user, cohort):
        raise PermissionDenied("คุณไม่มีสิทธิ์ส่งออกข้อมูลผู้เข้าพักของรุ่นนี้")
    students = CourseStudentLodging.objects.filter(cohort=cohort).select_related("room").order_by("room__code", "bed_number")

    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = f'attachment; filename="lodging_{cohort.slug}_{timezone.localdate().isoformat()}.csv"'

    writer = csv.writer(response)
    writer.writerow(["ลำดับ", "อาคาร", "เลขห้อง", "เตียงที่", "ยศ", "ชื่อ-นามสกุล", "หน่วยต้นสังกัด", "เบอร์โทรศัพท์", "วันที่จอง", "หมายเหตุ"])

    for idx, s in enumerate(students, 1):
        writer.writerow([
            idx,
            s.room.building,
            s.room.code,
            f"เตียง {s.bed_number}",
            s.rank,
            s.full_name,
            s.origin_unit,
            s.phone,
            timezone.localtime(s.booked_at).strftime("%d/%m/%Y %H:%M"),
            s.note,
        ])

    return response

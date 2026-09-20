import csv
import uuid
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from audit.services import audit
from resources.models import Resource
from .lodging_about_data import (
    ELECTRICITY_AIR_BAHT_PER_UNIT,
    ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH,
    MONTHLY_THRESHOLD_DAYS,
    RATES,
)
from .lodging_models import CourseLodgingCohort, CourseStudentLodging
from .lodging_services import (
    assign_lodging_bed,
    can_access_lodging_management,
    can_create_cohort,
    can_manage_cohort,
    check_in_student,
    generate_cohort_qr_svg,
    generate_line_share_url,
    get_canonical_public_url,
    normalize_phone,
    update_cohort_allocation,
)


# UX-17: Public dormitory showcase — no login required.
def lodging_about(request):
    """Public information page about the dormitory building.

    Presents static factual content (rooms, rates, floor plans, photos).
    Requires no authentication. Contains no student PII.
    No dependency on active cohort records.
    """
    context = {
        "rates": RATES,
        "electricity_air_baht_per_unit": ELECTRICITY_AIR_BAHT_PER_UNIT,
        "electricity_fan_flat_baht_per_month": ELECTRICITY_FAN_FLAT_BAHT_PER_MONTH,
        "monthly_threshold_days": MONTHLY_THRESHOLD_DAYS,
    }
    return render(request, "lodging/lodging_about.html", context)


def _masked_name(full_name: str) -> str:
    return " ".join(
        f"{part[:1]}***" if part else part
        for part in (full_name or "").split()
    )


def _masked_student_label(student: CourseStudentLodging) -> str:
    return f"{student.rank} {_masked_name(student.full_name)}".strip()


def _build_portal_context(cohort):
    students = CourseStudentLodging.objects.filter(cohort=cohort).select_related("room")
    students_by_room_bed = {
        (s.room_id, s.bed_number): s for s in students
    }

    rooms_data = []
    total_slots = 0
    occupied_slots = 0

    for room in cohort.rooms.all().order_by("building", "floor", "code").prefetch_related("photos"):
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

    # ห้องว่างมาก่อน ห้องเต็มทีหลัง (คงลำดับ building, floor, code ภายในแต่ละกลุ่ม)
    rooms_data.sort(key=lambda r: 1 if r["is_full"] else 0)

    return {
        "cohort": cohort,
        "rooms_data": rooms_data,
        "total_slots": total_slots,
        "occupied_slots": occupied_slots,
        "free_slots": max(0, total_slots - occupied_slots),
    }


def lodging_portal(request, slug):
    """หน้าจอเลือกห้องพักสำหรับนักเรียนหลักสูตร (ไม่ต้องเข้าสู่ระบบ สะดวกบนมือถือ)"""
    cohort = get_object_or_404(
        CourseLodgingCohort.objects.prefetch_related("rooms"),
        slug=slug,
        allocation_status=CourseLodgingCohort.AllocationStatus.ALLOCATED,
        is_active=True,
    )
    context = _build_portal_context(cohort)
    portal_path = reverse("bookings:lodging_portal", args=[cohort.slug])
    share_url = get_canonical_public_url(request, portal_path)
    context["share_url"] = share_url
    context["line_share_url"] = generate_line_share_url(cohort.title, share_url)
    if "lodging_modal_error" in request.session:
        context["modal_error"] = request.session.pop("lodging_modal_error")
        context["modal_data"] = request.session.pop("lodging_modal_data", {})
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

    def _respond_modal_error(err_msg):
        room_obj = None
        if room_id:
            try:
                room_obj = cohort.rooms.filter(pk=room_id).first()
            except (TypeError, ValueError):
                pass
        # เก็บข้อมูลและ error ใน session เพื่อให้ lodging_portal เปิด modal เดิมอัตโนมัติพร้อมคงข้อมูลที่กรอก
        request.session["lodging_modal_error"] = err_msg
        request.session["lodging_modal_data"] = {
            "room_id": str(room_id or ""),
            "room_code": room_obj.code if room_obj else "",
            "bed_number": str(bed_number_raw or ""),
            "rank": rank,
            "full_name": full_name,
            "origin_unit": origin_unit,
            "phone": request.POST.get("phone", "").strip(),
            "note": note,
        }
        # คง messages.error ไว้เป็น fallback สำหรับเบราว์เซอร์หรือกรณีที่ dialog ไม่เปิด
        messages.error(request, err_msg)
        return redirect("bookings:lodging_portal", slug=slug)

    if not all([room_id, bed_number_raw, rank, full_name, origin_unit, phone]):
        return _respond_modal_error("กรุณากรอกข้อมูลให้ครบทุกช่อง (ยศ, ชื่อ-สกุล, สังกัด, เบอร์โทร)")

    try:
        bed_number = int(bed_number_raw)
        if not (1 <= bed_number <= cohort.beds_per_room):
            raise ValueError
    except (TypeError, ValueError):
        return _respond_modal_error("หมายเลขเตียงไม่ถูกต้อง")

    try:
        student = assign_lodging_bed(cohort=cohort, room_id=room_id, bed_number=bed_number,
            rank=rank, full_name=full_name, origin_unit=origin_unit, phone=phone, note=note)
        room = student.room
    except (IntegrityError, ValidationError) as exc:
        return _respond_modal_error(" · ".join(exc.messages) if isinstance(exc, ValidationError)
            else "เกิดข้อผิดพลาดในการบันทึก หรือเตียงนี้มีผู้จองแล้ว กรุณาลองใหม่อีกครั้ง")

    messages.success(request, f"ลงทะเบียนจองห้อง {room.code} เตียง {bed_number} สำเร็จ!")
    return redirect("bookings:lodging_pass", slug=slug, student_id=student.id)


def lodging_pass(request, slug, student_id):
    """บัตรยืนยันการเข้าพักสำหรับนักเรียนแคปหน้าจอไว้เป็นหลักฐาน"""
    cohort = get_object_or_404(CourseLodgingCohort, slug=slug)
    student = get_object_or_404(CourseStudentLodging.objects.select_related("room", "cohort"), pk=student_id, cohort=cohort)
    roommates = CourseStudentLodging.objects.filter(
        cohort=cohort, room=student.room
    ).exclude(pk=student.pk).order_by("bed_number")

    pass_path = reverse("bookings:lodging_pass", args=[cohort.slug, student.id])
    pass_url = get_canonical_public_url(request, pass_path)
    line_share_url = generate_line_share_url(
        f"บัตรรายงานตัวเข้าที่พัก {student.room.code} (เตียง {student.bed_number}) - {cohort.title}",
        pass_url,
    )

    response = render(
        request,
        "lodging/student_pass.html",
        {
            "cohort": cohort,
            "student": student,
            "roommates": roommates,
            "pass_url": pass_url,
            "line_share_url": line_share_url,
        },
    )
    response["Cache-Control"] = "private, no-store, must-revalidate"
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
    if not can_access_lodging_management(request.user):
        raise PermissionDenied("คุณไม่มีสิทธิ์จัดการรอบที่พัก")
    can_create = can_create_cohort(request.user)
    cohorts = CourseLodgingCohort.objects.all().prefetch_related("rooms", "students")
    if not (request.user.is_superuser or request.user.has_perm("bookings.change_courselodgingcohort")):
        cohorts = cohorts.filter(supervisor=request.user)
    lodging_rooms = Resource.objects.filter(
        resource_type=Resource.Type.ROOM,
        room_category=Resource.Category.LODGING,
        status=Resource.Status.ACTIVE,
    ).order_by("building", "code")

    if request.method == "POST":
        if not can_create:
            raise PermissionDenied("คุณไม่มีสิทธิ์สร้างรอบที่พัก")
        title = request.POST.get("title", "").strip()
        slug = request.POST.get("slug", "").strip().lower() or f"course-{uuid.uuid4().hex[:12]}"
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
                        is_active=request.POST.get("publication", "open") == "open",
                        beds_per_room=beds_per_room,
                        supervisor=request.user,
                        title=title,
                        note=note,
                        actor=request.user,
                    )
                    messages.success(request, f"สร้างรอบจอง '{title}' เรียบร้อยแล้ว กรุณาตรวจสถานะเปิดรับจองก่อนส่งลิงก์")
                    return redirect("bookings:lodging_cohort_detail", slug=cohort.slug)
            except (ValueError, ValidationError, IntegrityError, PermissionDenied) as e:
                messages.error(request, f"เกิดข้อผิดพลาด: {e}")

    return render(
        request,
        "lodging/manage_list.html",
        {
            "cohorts": cohorts,
            "lodging_rooms": lodging_rooms,
            "can_create": can_create,
        },
    )


@login_required
def lodging_cohort_detail(request, slug):
    """ดูรายละเอียดและรายชื่อนักเรียนในรอบหลักสูตร"""
    cohort = get_object_or_404(CourseLodgingCohort.objects.prefetch_related("rooms"), slug=slug)
    if not can_manage_cohort(request.user, cohort):
        raise PermissionDenied("คุณไม่มีสิทธิ์ดูข้อมูลผู้เข้าพักของรุ่นนี้")
    students = (
        CourseStudentLodging.objects.filter(cohort=cohort)
        .select_related("room", "checked_in_by")
        .order_by("room__code", "bed_number")
    )

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

    audit(
        request.user,
        "bookings.courselodgingcohort",
        cohort.pk,
        "lodging_csv_exported",
        after={"slug": cohort.slug, "student_count": students.count()},
    )
    return response


def lodging_checkin(request, student_id):
    """หน้า check-in ด้วย QR บนบัตร — ผู้ไม่มีสิทธิ์เห็นเฉพาะสถานะบัตร (masked),
    ผู้มีสิทธิ์ (superuser/ผู้มี permission/ผู้กำกับหลักสูตรของรุ่นนี้) เห็นข้อมูลเต็มและยืนยันรายงานตัวได้
    """
    student = get_object_or_404(
        CourseStudentLodging.objects.select_related("room", "cohort"), pk=student_id
    )
    cohort = student.cohort
    has_permission = can_manage_cohort(request.user, cohort)

    if request.method == "POST":
        # ตรวจสิทธิ์อยู่ใน check_in_student() เอง (services.py) — ถ้าไม่มีสิทธิ์จะ raise
        # PermissionDenied ซึ่ง Django แปลงเป็น HTTP 403 จริงให้อัตโนมัติ ไม่ใช่แค่ซ่อนปุ่ม
        try:
            check_in_student(student, actor=request.user)
            messages.success(request, f"ยืนยันรายงานตัว {student.rank} {student.full_name} เรียบร้อยแล้ว")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
        return redirect("bookings:lodging_checkin", student_id=student.id)

    context = {
        "student": student,
        "cohort": cohort,
        "has_permission": has_permission,
        "masked_label": _masked_student_label(student),
    }
    return render(request, "lodging/checkin.html", context)


def lodging_checkin_qr_svg(request, student_id):
    """QR SVG ชี้ไปหน้า check-in ของนักเรียนคนนี้ (ไม่ต้องล็อกอิน — ฝังในบัตร digital pass สาธารณะ)"""
    student = get_object_or_404(CourseStudentLodging, pk=student_id)
    path = reverse("bookings:lodging_checkin", args=[student.id])
    url = get_canonical_public_url(request, path)
    response = HttpResponse(generate_cohort_qr_svg(url), content_type="image/svg+xml")
    response["Content-Disposition"] = f'inline; filename="checkin_{student.id}.svg"'
    response["X-Content-Type-Options"] = "nosniff"
    return response

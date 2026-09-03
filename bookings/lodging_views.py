import csv
from datetime import datetime
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from resources.models import Resource
from .lodging_models import CourseLodgingCohort, CourseStudentLodging


def lodging_portal(request, slug):
    """หน้าจอเลือกห้องพักสำหรับนักเรียนหลักสูตร (ไม่ต้องเข้าสู่ระบบ สะดวกบนมือถือ)"""
    cohort = get_object_or_404(
        CourseLodgingCohort.objects.prefetch_related("rooms"),
        slug=slug,
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
                    "student": student,
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
    cohort = get_object_or_404(CourseLodgingCohort, slug=slug, is_active=True)
    room_id = request.POST.get("room_id")
    bed_number_raw = request.POST.get("bed_number")
    rank = request.POST.get("rank", "").strip()
    full_name = request.POST.get("full_name", "").strip()
    origin_unit = request.POST.get("origin_unit", "").strip()
    phone = request.POST.get("phone", "").strip()
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

    room = get_object_or_404(cohort.rooms, pk=room_id)

    try:
        with transaction.atomic():
            # ตรวจสอบว่าเตียงนี้ในห้องนี้มีผู้จองแล้วหรือไม่
            existing_bed = CourseStudentLodging.objects.filter(
                cohort=cohort, room=room, bed_number=bed_number
            ).exists()
            if existing_bed:
                messages.error(request, f"ขออภัย ห้อง {room.code} เตียง {bed_number} มีเพื่อนร่วมรุ่นเพิ่งจองไปแล้ว กรุณาเลือกเตียงอื่น")
                return redirect("bookings:lodging_portal", slug=slug)

            # ตรวจสอบว่าเบอร์โทรนี้เคยจองไปแล้วหรือไม่
            existing_student = CourseStudentLodging.objects.filter(
                cohort=cohort, phone=phone
            ).first()
            if existing_student:
                messages.warning(request, f"หมายเลขโทรศัพท์ {phone} ได้ลงทะเบียนไว้แล้วที่ห้อง {existing_student.room.code} เตียง {existing_student.bed_number}")
                return redirect("bookings:lodging_pass", slug=slug, student_id=existing_student.id)

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
    except IntegrityError:
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

    return render(
        request,
        "lodging/student_pass.html",
        {
            "cohort": cohort,
            "student": student,
            "roommates": roommates,
        },
    )


@login_required
def lodging_manage(request):
    """หน้าสำหรับผู้กำกับหลักสูตร: ดูและสร้างรอบการจองที่พัก"""
    cohorts = CourseLodgingCohort.objects.all().prefetch_related("rooms", "students")
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
                    cohort = CourseLodgingCohort.objects.create(
                        title=title,
                        slug=slug,
                        supervisor=request.user,
                        unit=request.user.unit,
                        check_in_date=check_in_date,
                        check_out_date=check_out_date,
                        beds_per_room=beds_per_room,
                        note=note,
                    )
                    cohort.rooms.set(Resource.objects.filter(id__in=room_ids))
                    messages.success(request, f"สร้างรอบจอง '{title}' เรียบร้อยแล้ว สามารถคัดลอกลิงก์ส่งให้นักเรียนได้ทันที")
                    return redirect("bookings:lodging_cohort_detail", slug=cohort.slug)
            except Exception as e:
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

    share_url = request.build_absolute_uri(reverse("bookings:lodging_portal", args=[cohort.slug]))

    return render(
        request,
        "lodging/cohort_detail.html",
        {
            "cohort": cohort,
            "students": students,
            "rooms_summary": rooms_summary,
            "share_url": share_url,
        },
    )


@login_required
def lodging_cohort_export_csv(request, slug):
    """ส่งออกรายชื่อผู้พักในหลักสูตรเป็นไฟล์ CSV (UTF-8 BOM สำหรับ Excel)"""
    cohort = get_object_or_404(CourseLodgingCohort, slug=slug)
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

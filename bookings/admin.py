from django.contrib import admin
from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from .models import (
    Booking,
    BookingAmendment,
    BookingResource,
    BookingSeries,
    CourseLodgingCohort,
    CourseStudentLodging,
    Preemption,
    ReferenceValue,
    SeriesSkip,
)
from .lodging_services import update_cohort_allocation


class CourseLodgingCohortAdminForm(forms.ModelForm):
    class Meta:
        model = CourseLodgingCohort
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        rooms = list(cleaned.get("rooms") or [])
        status = cleaned.get("allocation_status")
        is_active = cleaned.get("is_active")
        check_in = cleaned.get("check_in_date")
        check_out = cleaned.get("check_out_date")
        if check_in and check_out and check_out < check_in:
            self.add_error("check_out_date", "วันที่สิ้นสุดการเข้าพักต้องไม่ก่อนวันที่เริ่มเข้าพัก")
        if status == CourseLodgingCohort.AllocationStatus.ALLOCATED and not rooms:
            self.add_error("rooms", "สถานะจัดสรรห้องพักต้องมีห้องอย่างน้อย 1 ห้อง")
        if status == CourseLodgingCohort.AllocationStatus.RELEASED and is_active:
            self.add_error("is_active", "รอบที่ปลดการสงวนห้องแล้วต้องไม่เปิดรับจอง")
        return cleaned


class BookingResourceInline(admin.TabularInline):
    model = BookingResource
    extra = 0
    readonly_fields = ("resource", "amendment", "hold", "released_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # ช่วงถือครองสร้างผ่าน services.place_holds เท่านั้น


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("title", "room", "start_at", "end_at", "unit", "requester", "request_status", "usage_status", "visibility")
    list_filter = ("request_status", "usage_status", "visibility", "room", "unit")
    search_fields = ("title", "responsible_name", "requester__username", "room__code")
    date_hierarchy = "start_at"
    readonly_fields = ("id", "revision", "created_at", "updated_at", "submitted_at", "is_urgent", "sla_escalated_at", "decision_reason", "series", "series_index")
    autocomplete_fields = ("requester",)
    filter_horizontal = ("equipment",)
    inlines = [BookingResourceInline]
    fieldsets = (
        ("กิจกรรม", {"fields": ("title", "purpose", "room", ("start_at", "end_at"), ("attendees", "attendee_level"))}),
        ("ผู้ขอ", {"fields": ("requester", "unit", ("responsible_name", "responsible_phone"))}),
        ("รายละเอียด", {"fields": ("layout", "fixed_equipment_needed", "equipment", ("has_external_attendees", "external_attendees_note"), "visibility", "note")}),
        ("สถานะ", {"fields": (("request_status", "usage_status"), "is_urgent", "revision", "submitted_at", "sla_escalated_at", "decision_reason")}),
        ("ระบบ", {"classes": ("collapse",), "fields": ("id", "series", "series_index", "created_at", "updated_at")}),
    )


class SeriesSkipInline(admin.TabularInline):
    model = SeriesSkip
    extra = 0
    readonly_fields = ("occur_date", "kind", "reason")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BookingSeries)
class BookingSeriesAdmin(admin.ModelAdmin):
    list_display = ("id", "room", "created_by", "freq", "start_date", "end_date", "requested_count", "created_at")
    list_filter = ("freq", "room")
    search_fields = ("id", "room__code", "created_by__username")
    readonly_fields = (
        "id", "room", "created_by", "unit", "freq", "weekdays", "custom_dates", "start_date",
        "end_date", "requested_count", "time_start", "time_end", "created_at",
    )
    inlines = [SeriesSkipInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BookingAmendment)
class BookingAmendmentAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "status", "submitted_by", "proposed_room", "submitted_at", "decided_at")
    list_filter = ("status", "is_urgent", "submitted_at")
    search_fields = ("id", "booking__title", "booking__room__code", "submitted_by__username", "reason")
    readonly_fields = tuple(field.name for field in BookingAmendment._meta.fields) + ("proposed_equipment",)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Preemption)
class PreemptionAdmin(admin.ModelAdmin):
    list_display = ("reference_no", "displaced", "incoming", "replacement", "ordered_by", "created_at", "acknowledged_at", "deemed_acknowledged")
    list_filter = ("deemed_acknowledged", "created_at")
    search_fields = ("reference_no", "reason", "displaced__title", "ordered_by__username")
    readonly_fields = tuple(field.name for field in Preemption._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReferenceValue)
class ReferenceValueAdmin(admin.ModelAdmin):
    list_display = ("field", "value", "order", "is_active")
    list_filter = ("field", "is_active")
    search_fields = ("value",)
    list_editable = ("order", "is_active")
    ordering = ("field", "order", "value")


class CourseStudentLodgingInline(admin.TabularInline):
    model = CourseStudentLodging
    extra = 0
    readonly_fields = ("booked_at",)


@admin.register(CourseLodgingCohort)
class CourseLodgingCohortAdmin(admin.ModelAdmin):
    form = CourseLodgingCohortAdminForm
    list_display = ("title", "slug", "supervisor", "unit", "check_in_date", "check_out_date", "beds_per_room", "allocation_status", "is_active", "created_at")
    list_filter = ("allocation_status", "is_active", "unit", "check_in_date")
    search_fields = ("title", "slug", "supervisor__username")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("rooms",)
    inlines = [CourseStudentLodgingInline]

    def save_model(self, request, obj, form, change):
        try:
            update_cohort_allocation(
                cohort=obj,
                rooms=form.cleaned_data.get("rooms", []),
                check_in_date=form.cleaned_data["check_in_date"],
                check_out_date=form.cleaned_data["check_out_date"],
                allocation_status=form.cleaned_data["allocation_status"],
                is_active=form.cleaned_data["is_active"],
                beds_per_room=form.cleaned_data["beds_per_room"],
                supervisor=form.cleaned_data.get("supervisor"),
                title=form.cleaned_data.get("title"),
                note=form.cleaned_data.get("note"),
                actor=request.user,
            )
        except (ValidationError, PermissionDenied) as exc:
            obj._lodging_save_failed = True
            messages.error(request, f"ไม่สามารถบันทึกรอบที่พักได้: {exc}")

    def save_related(self, request, form, formsets, change):
        if getattr(form.instance, "_lodging_save_failed", False):
            return
        for formset in formsets:
            self.save_formset(request, form, formset, change=change)


@admin.register(CourseStudentLodging)
class CourseStudentLodgingAdmin(admin.ModelAdmin):
    list_display = ("rank", "full_name", "cohort", "room", "bed_number", "origin_unit", "phone", "booked_at")
    list_filter = ("cohort", "room", "rank")
    search_fields = ("full_name", "origin_unit", "phone", "room__code")
    readonly_fields = ("booked_at",)

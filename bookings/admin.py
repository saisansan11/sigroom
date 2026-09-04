from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseRedirect
from django.urls import reverse
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
            obj._lodging_error = str(exc)

    def save_related(self, request, form, formsets, change):
        # เมื่อ update_cohort_allocation ล้มเหลว obj ยังไม่ถูกบันทึกจริง จึงข้าม
        # การบันทึก inline formset แต่ยังต้องตั้งค่า new_objects/changed_objects/
        # deleted_objects ให้ formset เพราะ construct_change_message() (เรียกโดย
        # Django เสมอ ไม่ว่า save จะสำเร็จหรือไม่) อ่านแอตทริบิวต์เหล่านี้โดยตรง
        if getattr(form.instance, "_lodging_error", None):
            for formset in formsets:
                formset.new_objects = []
                formset.changed_objects = []
                formset.deleted_objects = []
            return
        for formset in formsets:
            self.save_formset(request, form, formset, change=change)

    def _lodging_error_redirect(self, request, obj):
        messages.error(request, f"ไม่สามารถบันทึกรอบที่พักได้: {obj._lodging_error}")
        if obj._state.adding:
            url_name = f"admin:{obj._meta.app_label}_{obj._meta.model_name}_add"
            return HttpResponseRedirect(reverse(url_name))
        url_name = f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change"
        return HttpResponseRedirect(reverse(url_name, args=[obj.pk]))

    def response_add(self, request, obj, post_url_continue=None):
        if getattr(obj, "_lodging_error", None):
            return self._lodging_error_redirect(request, obj)
        return super().response_add(request, obj, post_url_continue)

    def response_change(self, request, obj):
        if getattr(obj, "_lodging_error", None):
            return self._lodging_error_redirect(request, obj)
        return super().response_change(request, obj)

    def log_addition(self, request, obj, message):
        if getattr(obj, "_lodging_error", None):
            return None
        return super().log_addition(request, obj, message)

    def log_change(self, request, obj, message):
        if getattr(obj, "_lodging_error", None):
            return None
        return super().log_change(request, obj, message)


@admin.register(CourseStudentLodging)
class CourseStudentLodgingAdmin(admin.ModelAdmin):
    list_display = ("rank", "full_name", "cohort", "room", "bed_number", "origin_unit", "phone", "booked_at")
    list_filter = ("cohort", "room", "rank")
    search_fields = ("full_name", "origin_unit", "phone", "room__code")
    readonly_fields = ("booked_at",)

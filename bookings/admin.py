from django.contrib import admin

from .models import Booking, BookingResource


class BookingResourceInline(admin.TabularInline):
    model = BookingResource
    extra = 0
    readonly_fields = ("resource", "hold", "released_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False  # ช่วงถือครองสร้างผ่าน services.place_holds เท่านั้น


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("title", "room", "start_at", "end_at", "unit", "requester", "request_status", "usage_status", "visibility")
    list_filter = ("request_status", "usage_status", "visibility", "room", "unit")
    search_fields = ("title", "responsible_name", "requester__username", "room__code")
    date_hierarchy = "start_at"
    readonly_fields = ("id", "revision", "created_at", "updated_at", "submitted_at", "is_urgent", "sla_escalated_at", "decision_reason")
    autocomplete_fields = ("requester",)
    filter_horizontal = ("equipment",)
    inlines = [BookingResourceInline]
    fieldsets = (
        ("กิจกรรม", {"fields": ("title", "purpose", "room", ("start_at", "end_at"), ("attendees", "attendee_level"))}),
        ("ผู้ขอ", {"fields": ("requester", "unit", ("responsible_name", "responsible_phone"))}),
        ("รายละเอียด", {"fields": ("layout", "fixed_equipment_needed", "equipment", ("has_external_attendees", "external_attendees_note"), "visibility", "note")}),
        ("สถานะ", {"fields": (("request_status", "usage_status"), "is_urgent", "revision", "submitted_at", "sla_escalated_at", "decision_reason")}),
        ("ระบบ", {"classes": ("collapse",), "fields": ("id", "created_at", "updated_at")}),
    )

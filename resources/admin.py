from django.contrib import admin

from .models import Blackout, Resource, ResourceApprover, ResourceOutage, ResourceRule


class ResourceRuleInline(admin.StackedInline):
    model = ResourceRule
    can_delete = False
    filter_horizontal = ("allowed_units",)
    fieldsets = (
        ("การอนุมัติ", {"fields": ("approval_policy", "allowed_units")}),
        ("เวลา", {"fields": (("max_advance_days", "cancel_cutoff_hours"), ("buffer_before_min", "buffer_after_min"),
                              ("service_start", "service_end"), ("min_duration_min", "max_duration_min"))}),
        ("จองเป็นชุด", {"fields": (("allow_series", "max_series_occurrences"),)}),
    )


class ResourceApproverInline(admin.TabularInline):
    model = ResourceApprover
    extra = 1
    autocomplete_fields = ("user",)


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "resource_type", "room_category", "building", "capacity", "owner_unit", "status")
    list_filter = ("resource_type", "room_category", "building", "status", "owner_unit")
    search_fields = ("code", "name", "building")
    filter_horizontal = ("custodians",)
    inlines = [ResourceRuleInline, ResourceApproverInline]
    fieldsets = (
        (None, {"fields": (("resource_type", "code"), "name", "status")}),
        ("ที่ตั้ง", {"fields": (("building", "floor"), "location_note")}),
        ("คุณลักษณะห้อง", {"fields": ("room_category", "capacity", "fixed_equipment", "layouts")}),
        ("ผู้รับผิดชอบ", {"fields": ("owner_unit", "custodians")}),
    )


@admin.register(Blackout)
class BlackoutAdmin(admin.ModelAdmin):
    list_display = ("title", "start_at", "end_at", "scope", "building", "room_category")
    list_filter = ("scope", "building", "room_category")
    search_fields = ("title", "building", "rooms__code")
    filter_horizontal = ("rooms",)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ResourceOutage)
class ResourceOutageAdmin(admin.ModelAdmin):
    list_display = ("resource", "start_at", "end_at", "reason", "created_by", "ended_early_at")
    list_filter = ("resource", "ended_early_at")
    search_fields = ("resource__code", "reason", "created_by__username")
    autocomplete_fields = ("resource", "created_by")

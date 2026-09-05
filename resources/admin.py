from django.conf import settings
from django.contrib import admin
from django.utils.html import format_html

from .models import Blackout, Resource, ResourceApprover, ResourceOutage, ResourcePhoto, ResourceRule
from .services import delete_room_photo, save_room_photo


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


class ResourcePhotoInline(admin.TabularInline):
    """อัปโหลดรูปห้องได้หลายรูป จัดลำดับได้ (งาน v6-c) — save/delete ทุกแถววิ่งผ่าน
    resources.services.save_room_photo()/delete_room_photo() เท่านั้น (ดู ResourceAdmin.save_formset)
    เมื่อ settings.ROOM_PHOTO_UPLOAD_ENABLED เป็น False (C1 กรณีที่ 3) จะซ่อนช่องอัปโหลดและแสดง
    ข้อความไทยแทนที่หัวข้อ inline นี้
    """

    model = ResourcePhoto
    fields = ("image_preview", "image", "caption", "order", "is_cover")
    readonly_fields = ("image_preview",)
    ordering = ("order", "id")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.ROOM_PHOTO_UPLOAD_ENABLED:
            self.verbose_name_plural = (
                "รูปห้อง — ยังไม่ได้ตั้งค่าที่เก็บรูป (GS_BUCKET_NAME) อัปโหลดได้เมื่อตั้งค่าตาม C5 แล้ว"
            )

    def get_extra(self, request, obj=None, **kwargs):
        return 1 if settings.ROOM_PHOTO_UPLOAD_ENABLED else 0

    def has_add_permission(self, request, obj=None):
        return settings.ROOM_PHOTO_UPLOAD_ENABLED

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if not settings.ROOM_PHOTO_UPLOAD_ENABLED and "image" in fields:
            fields.remove("image")
        return fields

    @admin.display(description="ตัวอย่าง")
    def image_preview(self, obj):
        if obj and obj.pk and obj.image:
            return format_html('<img src="{}" alt="" style="max-height:60px;border-radius:.25rem;">', obj.image.url)
        return "—"


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "resource_type", "room_category", "building", "capacity", "owner_unit", "status")
    list_filter = ("resource_type", "room_category", "building", "status", "owner_unit")
    search_fields = ("code", "name", "building")
    filter_horizontal = ("custodians",)
    inlines = [ResourceRuleInline, ResourceApproverInline, ResourcePhotoInline]
    fieldsets = (
        (None, {"fields": (("resource_type", "code"), "name", "status")}),
        ("ที่ตั้ง", {"fields": (("building", "floor"), "location_note")}),
        ("คุณลักษณะห้อง", {"fields": ("room_category", "capacity", "fixed_equipment", "layouts")}),
        ("ผู้รับผิดชอบ", {"fields": ("owner_unit", "custodians")}),
    )

    def save_formset(self, request, form, formset, change):
        if formset.model is not ResourcePhoto:
            super().save_formset(request, form, formset, change)
            return
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            delete_room_photo(obj)
        for obj in instances:
            matching_form = next(f for f in formset.forms if f.instance is obj)
            raw_image = matching_form.cleaned_data.get("image") if "image" in matching_form.changed_data else None
            new_image = raw_image or None
            save_room_photo(
                resource=obj.resource,
                image=new_image,
                caption=obj.caption,
                order=obj.order,
                is_cover=obj.is_cover,
                photo=obj if obj.pk else None,
            )
        formset.save_m2m()


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

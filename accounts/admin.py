from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Unit, User


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "parent", "is_active")
    search_fields = ("code", "name")
    list_filter = ("is_active",)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "display_name", "email", "unit", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "unit", "is_infosec_officer")
    search_fields = ("username", "email", "first_name", "last_name", "service_number")
    ordering = ("username",)
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("ข้อมูลกำลังพล", {"fields": ("rank", "first_name", "last_name", "service_number", "position", "phone", "email", "unit")}),
        ("สิทธิ์", {"fields": ("is_active", "is_staff", "is_superuser", "is_infosec_officer", "must_change_password", "groups", "user_permissions")}),
        ("วันที่", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "rank", "first_name", "last_name", "unit", "must_change_password", "password1", "password2")}),
    )

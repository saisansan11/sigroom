from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("at", "actor", "action", "entity", "entity_id", "ip")
    list_filter = ("action", "entity", "at")
    search_fields = ("actor__username", "entity", "entity_id", "action", "ip")
    readonly_fields = ("at", "actor", "entity", "entity_id", "action", "before", "after", "ip")
    date_hierarchy = "at"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in {"GET", "HEAD", "OPTIONS"} and self.has_view_permission(request, obj)

    def has_view_permission(self, request, obj=None):
        return bool(request.user.is_superuser or request.user.is_infosec_officer)


from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "text", "created_at", "read_at")
    list_filter = ("read_at", "created_at")
    search_fields = ("user__username", "text")
    readonly_fields = ("user", "text", "url", "booking", "created_at", "read_at")

    def has_add_permission(self, request):
        return False

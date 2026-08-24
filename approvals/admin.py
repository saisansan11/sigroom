from django.contrib import admin

from .models import Approval, ApproverDelegation


@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ("booking", "amendment", "action", "acted_by", "on_behalf_of", "acted_at")
    list_filter = ("action", "acted_at")
    search_fields = ("booking__title", "booking__room__code", "acted_by__username", "reason")
    readonly_fields = ("booking", "amendment", "action", "acted_by", "on_behalf_of", "reason", "acted_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApproverDelegation)
class ApproverDelegationAdmin(admin.ModelAdmin):
    list_display = ("delegator", "delegate", "start_date", "end_date", "created_at")
    search_fields = ("delegator__username", "delegate__username")
    autocomplete_fields = ("delegator", "delegate")

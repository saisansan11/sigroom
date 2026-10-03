from django.urls import reverse

from approvals.services import has_approval_role, pending_for
from reports.services import can_access_reports
from usage.services import can_manage_usage
from bookings.lodging_services import can_access_lodging_management
from bookings.online_teaching import can_book_online_teaching
from bookings.role_home import SERVICE_LABELS, managed_services

from .services import unread_count


def navigation_counts(request):
    if not getattr(request.user, "is_authenticated", False):
        return {}
    can_access = has_approval_role(request.user)
    services = managed_services(request.user)
    managed_nav = [
        (slug, SERVICE_LABELS[slug], reverse("bookings:service_staff_entry", args=[slug]))
        for slug in services
    ]
    return {
        "nav_unread_count": getattr(request, "_nav_unread_count", None) if getattr(request, "_nav_unread_count", None) is not None else unread_count(request.user),
        "nav_can_access_approvals": can_access,
        "nav_pending_approval_count": len(pending_for(request.user)) if can_access else 0,
        "nav_can_manage_usage": can_manage_usage(request.user),
        "nav_can_access_reports": can_access_reports(request.user),
        "nav_can_manage_lodging": can_access_lodging_management(request.user),
        "nav_can_book_online": can_book_online_teaching(request.user),
        "nav_managed_services": managed_nav,
    }

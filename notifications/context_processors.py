from approvals.services import has_approval_role, pending_for
from reports.services import can_access_reports
from usage.services import can_manage_usage
from bookings.lodging_services import can_create_cohort

from .services import unread_count


def navigation_counts(request):
    if not getattr(request.user, "is_authenticated", False):
        return {}
    can_access = has_approval_role(request.user)
    return {
        "nav_unread_count": unread_count(request.user),
        "nav_can_access_approvals": can_access,
        "nav_pending_approval_count": len(pending_for(request.user)) if can_access else 0,
        "nav_can_manage_usage": can_manage_usage(request.user),
        "nav_can_access_reports": can_access_reports(request.user),
        "nav_can_manage_lodging": can_create_cohort(request.user),
    }

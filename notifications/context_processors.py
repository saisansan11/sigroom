from django.urls import reverse

from approvals.services import has_approval_role, pending_for
from reports.services import can_access_reports
from usage.services import can_manage_usage
from bookings.lodging_services import can_access_lodging_management
from bookings.online_teaching import can_book_online_teaching
from bookings.role_home import NAV_SERVICE_LABELS, SERVICE_LABELS, current_service, managed_services, service_booking_url

from .push import push_enabled
from .services import unread_count


def navigation_counts(request):
    service = current_service(request)
    links = []
    match = getattr(request, "resolver_match", None)
    name = match.url_name if match else None
    if service:
        links.append({
            "label": "จองห้องพัก" if service == "lodging" else "จองห้อง",
            "url": service_booking_url(service),
            "active": name in {
                "book_search", "book_form", "online_teaching_home", "online_teaching_book",
                "lodging_start", "lodging_index", "lodging_general_request",
            },
        })
        if service in {"classroom", "meeting"}:
            links.append({"label": "สถานะห้อง", "url": f"{reverse('bookings:calendar')}?category={service}", "active": name == "calendar"})
        if service != "lodging":
            links.append({"label": "การจองของฉัน", "url": f"{reverse('bookings:my_bookings')}?service={service}", "active": name == "my_bookings"})
        elif name == "lodging_general_request_status":
            # สถานะคำขอสาธารณะต้องใช้ token เดิมของรายการนี้ ไม่มีหน้ารวมคำขอผู้พัก
            links.append({"label": "สถานะคำขอ", "url": reverse("bookings:lodging_general_request_status", kwargs=match.kwargs), "active": True})
    context = {
        "nav_service": service, "nav_service_label": NAV_SERVICE_LABELS.get(service, ""),
        "nav_service_links": links, "nav_service_booking_url": service_booking_url(service),
    }
    if not getattr(request.user, "is_authenticated", False):
        return context
    can_access = has_approval_role(request.user)
    services = managed_services(request.user)
    managed_nav = [
        (slug, SERVICE_LABELS[slug], reverse("bookings:service_staff_entry", args=[slug]))
        for slug in services
    ]
    enabled = push_enabled()
    context.update({
        "webpush_enabled": enabled,
        "webpush_public_key": settings_public_key() if enabled else "",
        "nav_unread_count": getattr(request, "_nav_unread_count", None) if getattr(request, "_nav_unread_count", None) is not None else unread_count(request.user),
        "nav_can_access_approvals": can_access,
        "nav_pending_approval_count": len(pending_for(request.user)) if can_access else 0,
        "nav_can_manage_usage": can_manage_usage(request.user),
        "nav_can_access_reports": can_access_reports(request.user),
        "nav_can_manage_lodging": can_access_lodging_management(request.user),
        "nav_can_book_online": can_book_online_teaching(request.user),
        "nav_managed_services": managed_nav,
    })
    return context


def settings_public_key():
    from django.conf import settings

    return settings.WEBPUSH_VAPID_PUBLIC_KEY

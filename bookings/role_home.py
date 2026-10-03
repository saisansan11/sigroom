from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from resources.models import Resource
from .lodging_services import can_access_lodging_management

SERVICE_LODGING = "lodging"
SERVICE_ONLINE = "online"
SERVICE_LEARNING = "learning"
SERVICE_ORDER = (SERVICE_LODGING, SERVICE_ONLINE, SERVICE_LEARNING)

SERVICE_LABELS = {
    SERVICE_LODGING: "ห้องพัก",
    SERVICE_ONLINE: "ห้องสอนออนไลน์",
    SERVICE_LEARNING: "ห้องเรียน/ประชุม",
}

SERVICE_CATEGORIES = {
    SERVICE_ONLINE: (Resource.Category.ONLINE,),
    SERVICE_LEARNING: (
        Resource.Category.CLASSROOM,
        Resource.Category.LAB,
        Resource.Category.MEETING,
        Resource.Category.SPECIAL,
    ),
}


def managed_services(user) -> list[str]:
    """บริการที่ผู้ใช้ดูแล เรียง ห้องพัก → ออนไลน์ → ห้องเรียน/ประชุม."""
    if not getattr(user, "is_authenticated", False) or user.is_superuser:
        return []

    services = []
    if can_access_lodging_management(user):
        services.append(SERVICE_LODGING)

    managed_categories = set(
        user.custodied_resources.filter(resource_type=Resource.Type.ROOM).values_list("room_category", flat=True)
    )
    if managed_categories.intersection(SERVICE_CATEGORIES[SERVICE_ONLINE]):
        services.append(SERVICE_ONLINE)
    if managed_categories.intersection(SERVICE_CATEGORIES[SERVICE_LEARNING]):
        services.append(SERVICE_LEARNING)
    return services


@login_required
def role_home(request):
    services = managed_services(request.user)
    if not services:
        return redirect("bookings:lodging_about")
    return redirect("bookings:service_staff_entry", service=services[0])

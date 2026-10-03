from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from resources.models import Resource
from .lodging_services import can_access_lodging_management
from .online_teaching import can_book_online_teaching

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

# เมนูผู้จองแยกจากกลุ่มงานเจ้าหน้าที่เดิม (learning ดูแลหลายหมวดร่วมกัน)
NAV_SERVICE_LABELS = {
    "lodging": "ห้องพัก",
    "online": "ห้องสอนออนไลน์",
    "classroom": "ห้องเรียน",
    "meeting": "ห้องประชุม",
}
NAV_SERVICE_CATEGORIES = {
    "lodging": (Resource.Category.LODGING,),
    "online": (Resource.Category.ONLINE,),
    "classroom": (Resource.Category.CLASSROOM,),
    "meeting": (Resource.Category.MEETING, Resource.Category.SPECIAL),
}


def service_for_category(category):
    return next((service for service, categories in NAV_SERVICE_CATEGORIES.items() if category in categories), None)


def current_service(request):
    """สังกัดเมนูจาก route ที่ resolve แล้วและหมวดจริง ไม่เชื่อ header หรือ session."""
    match = getattr(request, "resolver_match", None)
    if not match or match.namespace != "bookings":
        return None
    name = match.url_name
    if name == "lodging_about":
        return None
    if name.startswith("lodging_"):
        return "lodging"
    if name in {"online_teaching_home", "online_teaching_book", "online_teaching_quick_book", "online_teaching_profile"}:
        return "online"
    if name == "service_staff_entry":
        service = match.kwargs.get("service")
        return service if service in NAV_SERVICE_LABELS else None
    if name == "book_search":
        category = request.GET.get("category", "").strip()
        return category if category in {"classroom", "meeting"} else None
    if name in {"calendar", "calendar_events"}:
        return service_for_category(request.GET.get("category", "").strip())
    if name == "my_bookings":
        service = request.GET.get("service", "").strip()
        return service if service in NAV_SERVICE_LABELS else None
    if name in {"book_form", "room_favorite_toggle", "series_preview", "series_create"}:
        category = (
            Resource.objects.filter(code=match.kwargs.get("code"), resource_type=Resource.Type.ROOM)
            .values_list("room_category", flat=True)
            .first()
        )
        return service_for_category(category)

    # หลังบันทึก/เปิดลิงก์ตรงไม่มี query ให้ยึดห้องจริงของรายการนั้น
    from .models import Booking, BookingAmendment, BookingSeries, Preemption

    object_routes = {
        "series_detail": (BookingSeries, "room__room_category"),
        "series_cancel_remaining": (BookingSeries, "room__room_category"),
        "booking_detail": (Booking, "room__room_category"),
        "booking_ics": (Booking, "room__room_category"),
        "booking_edit": (Booking, "room__room_category"),
        "booking_amend": (Booking, "room__room_category"),
        "booking_preempt": (Booking, "room__room_category"),
        "booking_cancel": (Booking, "room__room_category"),
        "booking_submit": (Booking, "room__room_category"),
        "booking_delete_draft": (Booking, "room__room_category"),
        "amendment_withdraw": (BookingAmendment, "booking__room__room_category"),
        "preemption_acknowledge": (Preemption, "displaced__room__room_category"),
    }
    if name in object_routes:
        model, category_path = object_routes[name]
        category = model.objects.filter(pk=match.kwargs.get("id")).values_list(category_path, flat=True).first()
        return service_for_category(category)
    return None


def service_booking_url(service):
    """จุดเริ่มจองของบริการเดียวกัน สำหรับเมนูและรายการส่วนตัว."""
    from django.urls import reverse

    if service == "online":
        return reverse("bookings:online_teaching_home")
    if service == "lodging":
        return reverse("bookings:lodging_start")
    url = reverse("bookings:book_search")
    return f"{url}?category={service}" if service in {"classroom", "meeting"} else url


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
        # ครูผู้สอน (ไม่ใช่ผู้ดูแลระบบ) เข้าหน้าจองห้องสอนออนไลน์ทันที ไม่ต้องผ่านหน้าเลือกบริการ
        if not request.user.is_superuser and can_book_online_teaching(request.user):
            return redirect("bookings:online_teaching_home")
        return redirect("bookings:lodging_about")
    return redirect("bookings:service_staff_entry", service=services[0])

"""
Views สำหรับศูนย์นโยบายและข้อกำหนดการใช้งาน (Policy Center) ของ SIGROOM
เข้าถึงได้โดยไม่ต้องเข้าสู่ระบบ (Public Access)
"""
from django.conf import settings
from django.shortcuts import render


def _policy_context(current_page: str, title: str):
    """สร้าง context พื้นฐานสำหรับหน้านโยบาย รวมถึงการตั้งค่าความปลอดภัยของเซสชัน"""
    session_cookie_name = getattr(
        settings,
        "SESSION_COOKIE_NAME",
        "__session" if getattr(settings, "DJANGO_SECURE", False) else "sessionid",
    )
    session_cookie_age = getattr(settings, "SESSION_COOKIE_AGE", 12 * 60 * 60)
    session_hours = session_cookie_age // 3600
    csrf_use_sessions = getattr(settings, "CSRF_USE_SESSIONS", False)
    django_secure = getattr(settings, "DJANGO_SECURE", False)

    return {
        "current_policy": current_page,
        "policy_title": title,
        "policy_date": "12 ตุลาคม 2569",
        "policy_version": "0.1 (ฉบับร่างสำหรับการพัฒนาระบบ)",
        "policy_status_badge": "ฉบับร่างรอยืนยัน (Draft — To Be Confirmed)",
        "session_cookie_name": session_cookie_name,
        "session_cookie_age_hours": session_hours,
        "csrf_use_sessions": csrf_use_sessions,
        "django_secure": django_secure,
    }


def privacy_view(request):
    """หน้านโยบายความเป็นส่วนตัว (/privacy) — 10 ส่วนตามข้อกำหนด"""
    context = _policy_context("privacy", "นโยบายความเป็นส่วนตัว")
    return render(request, "policy/privacy.html", context)


def cookies_view(request):
    """หน้านโยบายคุกกี้ (/cookies) — 5 ส่วนตามข้อกำหนด"""
    context = _policy_context("cookies", "นโยบายคุกกี้")
    return render(request, "policy/cookies.html", context)


def terms_view(request):
    """หน้านโยบายเว็บไซต์ / ข้อกำหนดการใช้งาน (/terms) — 9 ส่วนตามข้อกำหนด"""
    context = _policy_context("terms", "นโยบายเว็บไซต์")
    return render(request, "policy/terms.html", context)


def disclaimer_view(request):
    """หน้าข้อจำกัดความรับผิดชอบ (/disclaimer) — 6 ส่วนตามข้อกำหนด"""
    context = _policy_context("disclaimer", "ข้อจำกัดความรับผิดชอบ")
    return render(request, "policy/disclaimer.html", context)

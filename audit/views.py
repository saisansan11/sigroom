from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from .context import client_ip_is_trusted, forwarded_chain, request_ip

# header ที่แพลตฟอร์ม proxy/CDN มักใช้ส่ง IP ผู้ใช้ — แสดงเพื่อช่วยเลือกค่าตั้ง ไม่ได้เชื่อถืออัตโนมัติ
_CANDIDATE_MARKERS = ("FORWARDED", "CLIENT", "REAL_IP", "FAH", "FASTLY", "CONNECTING_IP", "TRUE_CLIENT")


@login_required
def client_ip_diagnostics(request):
    """หน้าตรวจว่า production ได้ IP ผู้ใช้จาก header ใด — เฉพาะผู้ดูแลระบบ เห็นเฉพาะคำขอของตัวเอง"""
    if not request.user.is_superuser:
        raise PermissionDenied("เฉพาะผู้ดูแลระบบ")
    chain = forwarded_chain(request)
    chain_rows = [
        {"value": value, "hops": len(chain) - index}
        for index, value in enumerate(chain)
    ]
    candidate_headers = sorted(
        (key[5:].replace("_", "-").title(), value)
        for key, value in request.META.items()
        if key.startswith("HTTP_") and key != "HTTP_X_FORWARDED_FOR" and any(m in key for m in _CANDIDATE_MARKERS)
    )
    response = render(
        request,
        "audit/client_ip.html",
        {
            "remote_addr": request.META.get("REMOTE_ADDR", ""),
            "chain_rows": chain_rows,
            "candidate_headers": candidate_headers,
            "configured_header": getattr(settings, "CLIENT_IP_HEADER", ""),
            "configured_hops": getattr(settings, "TRUSTED_PROXY_HOPS", None),
            "is_trusted": client_ip_is_trusted(),
            "resolved_ip": request_ip(request),
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response

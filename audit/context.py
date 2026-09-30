from contextvars import ContextVar

from django.conf import settings


_actor = ContextVar("audit_actor", default=None)
_ip = ContextVar("audit_ip", default="")


def set_audit_context(actor=None, ip=""):
    return _actor.set(actor), _ip.set(ip or "")


def reset_audit_context(tokens):
    actor_token, ip_token = tokens
    _actor.reset(actor_token)
    _ip.reset(ip_token)


def current_actor():
    actor = _actor.get()
    return actor if getattr(actor, "is_authenticated", False) else None


def current_ip():
    return _ip.get()


def client_ip_is_trusted() -> bool:
    """True เมื่อผู้ดูแลยืนยันแล้วว่าจะอ่าน IP จากตรงไหน (ดู CLIENT_IP_HEADER / TRUSTED_PROXY_HOPS)"""
    return bool(getattr(settings, "CLIENT_IP_HEADER", "")) or getattr(settings, "TRUSTED_PROXY_HOPS", None) is not None


def header_meta_key(name: str) -> str:
    return "HTTP_" + name.strip().upper().replace("-", "_")


def forwarded_chain(request) -> list[str]:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return [item.strip() for item in forwarded.split(",") if item.strip()]


def request_ip(request) -> str:
    """IP ผู้ใช้สำหรับ audit/throttle — ไม่เชื่อค่าที่ผู้ใช้ใส่เองเมื่อตั้งค่า proxy แล้ว"""
    if request is None:
        return ""
    remote = request.META.get("REMOTE_ADDR", "")
    header = getattr(settings, "CLIENT_IP_HEADER", "")
    if header:
        value = request.META.get(header_meta_key(header), "").split(",", 1)[0].strip()
        if value:
            return value[:45]
    chain = forwarded_chain(request)
    hops = getattr(settings, "TRUSTED_PROXY_HOPS", None)
    if hops is None:
        # ยังไม่ได้ยืนยันกับ production: คงพฤติกรรมเดิม (ค่าแรกสุด) และมีคำเตือนตอนเริ่มระบบ
        return (chain[0] if chain else remote)[:45]
    if hops <= 0 or len(chain) < hops:
        return remote[:45]
    return chain[-hops][:45]


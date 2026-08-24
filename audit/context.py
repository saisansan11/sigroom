from contextvars import ContextVar


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


def request_ip(request) -> str:
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",", 1)[0].strip() if forwarded else request.META.get("REMOTE_ADDR", ""))[:45]


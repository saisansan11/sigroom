from .context import request_ip, reset_audit_context, set_audit_context


class AuditActorMiddleware:
    """เก็บผู้ใช้และ IP ของ request ปัจจุบันให้ service/signal ระบุผู้กระทำได้"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tokens = set_audit_context(getattr(request, "user", None), request_ip(request))
        try:
            return self.get_response(request)
        finally:
            reset_audit_context(tokens)


def secure_configuration_warning(debug: bool, raw_value: str | None) -> str:
    if debug:
        return ""
    if raw_value is None:
        return (
            "DJANGO_DEBUG=0 แต่ไม่ได้กำหนด DJANGO_SECURE; ระบบจะเปิด HTTPS redirect โดยปริยาย "
            "ให้กำหนด DJANGO_SECURE=0 อย่างชัดเจนเฉพาะ pilot HTTP ใน LAN หรือ =1 เมื่อมี TLS"
        )
    if raw_value != "1":
        return (
            "DJANGO_SECURE=0 ขณะ DJANGO_DEBUG=0: อนุญาตเฉพาะ pilot HTTP ใน LAN เท่านั้น "
            "ห้ามใช้ค่านี้เมื่อเปิดผ่านอินเทอร์เน็ตหรือ production ที่มี TLS"
        )
    return ""


def password_reset_email_configuration_warning(debug: bool, backend: str, host: str) -> str:
    """เตือน configuration ที่อาจทำ token หลุด log หรือทำ reset email ใช้งานไม่ได้"""
    if debug:
        return ""
    if backend.endswith("console.EmailBackend"):
        return "Production ใช้ console EmailBackend: password-reset token อาจปรากฏใน application logs"
    if backend.endswith("smtp.EmailBackend") and not host:
        return "Production ใช้ SMTP EmailBackend แต่ EMAIL_HOST ว่าง: self-service password reset จะส่งอีเมลไม่ได้"
    return ""

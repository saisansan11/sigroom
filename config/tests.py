from .security import password_reset_email_configuration_warning, secure_configuration_warning


def test_secure_configuration_warns_for_both_pilot_traps():
    missing = secure_configuration_warning(False, None)
    insecure = secure_configuration_warning(False, "0")
    assert "ไม่ได้กำหนด DJANGO_SECURE" in missing
    assert "DJANGO_SECURE=0" in insecure and "LAN" in insecure
    assert secure_configuration_warning(False, "1") == ""
    assert secure_configuration_warning(True, None) == ""


def test_password_reset_email_configuration_warns_for_production_traps():
    console = password_reset_email_configuration_warning(
        False,
        "django.core.mail.backends.console.EmailBackend",
        "",
    )
    missing_host = password_reset_email_configuration_warning(
        False,
        "django.core.mail.backends.smtp.EmailBackend",
        "",
    )
    assert "token" in console and "logs" in console
    assert "EMAIL_HOST" in missing_host
    assert password_reset_email_configuration_warning(
        False,
        "django.core.mail.backends.smtp.EmailBackend",
        "smtp.internal.example",
    ) == ""
    assert password_reset_email_configuration_warning(
        True,
        "django.core.mail.backends.console.EmailBackend",
        "",
    ) == ""

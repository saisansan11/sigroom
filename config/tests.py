from .security import secure_configuration_warning


def test_secure_configuration_warns_for_both_pilot_traps():
    missing = secure_configuration_warning(False, None)
    insecure = secure_configuration_warning(False, "0")
    assert "ไม่ได้กำหนด DJANGO_SECURE" in missing
    assert "DJANGO_SECURE=0" in insecure and "LAN" in insecure
    assert secure_configuration_warning(False, "1") == ""
    assert secure_configuration_warning(True, None) == ""

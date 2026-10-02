"""ตั้งค่ากลางของ pytest: ไม่ให้เทสต้องพึ่ง manifest ของ collectstatic"""
import pytest


@pytest.fixture(autouse=True)
def _plain_static_storage(settings):
    """production ใช้ CompressedManifestStaticFilesStorage ซึ่งต้องมี manifest (หลัง collectstatic)
    ตอนเทส DEBUG=False จึงแจ้ง 'Missing staticfiles manifest entry' — สลับเป็น storage ธรรมดาเฉพาะตอนเทส"""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

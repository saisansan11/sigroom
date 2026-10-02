import pytest


@pytest.fixture(autouse=True)
def _plain_staticfiles_storage(settings):
    """ทดสอบไม่ต้อง collectstatic: ใช้ storage ธรรมดาแทน Manifest (production ใช้ hashed manifest)"""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }

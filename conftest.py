import pytest
from uuid import uuid4


@pytest.fixture(autouse=True)
def _plain_staticfiles_storage(settings):
    """ทดสอบไม่ต้อง collectstatic: ใช้ storage ธรรมดาแทน Manifest (production ใช้ hashed manifest)"""
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def enrolled_student(client):
    """Explicit PR6 test setup; never grant access to a cohort through its public QR."""
    from accounts.models import User
    from bookings.lodging_models import CourseStudentEnrollment

    def login(cohort, *, name="นักเรียน ทดสอบสิทธิ์", user=None):
        if user is None:
            suffix = uuid4().hex[:12]
            user = User.objects.create_user(username="student-test-" + suffix,
                email=suffix + "@signalschool.ac.th", first_name=name, is_lodging_student=True)
        CourseStudentEnrollment.objects.get_or_create(cohort=cohort, email=user.email,
            defaults={"user": user, "rank": "นนส.", "origin_unit": "โรงเรียนทหารสื่อสาร",
                      "phone": "080" + str(user.pk).zfill(7)})
        client.force_login(user)
        return user

    return login

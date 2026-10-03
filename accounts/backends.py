from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ValidationError

from .models import validate_allowed_email_domain


class UsernameOrEmailBackend(ModelBackend):
    """Authenticate an existing SIGROOM account by username or unit email."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_model = get_user_model()
        raw_identity = username or kwargs.get(user_model.USERNAME_FIELD)
        if raw_identity is None or password is None:
            return None

        identity = str(raw_identity).strip()
        try:
            if "@" in identity:
                email = identity.lower()
                try:
                    validate_allowed_email_domain(email)
                except ValidationError:
                    user = None
                else:
                    try:
                        user = user_model._default_manager.get(email__iexact=email)
                    except user_model.DoesNotExist:
                        user = None
            else:
                try:
                    user = user_model._default_manager.get_by_natural_key(identity)
                except user_model.DoesNotExist:
                    user = None
        except user_model.MultipleObjectsReturned:
            # Email is unique by schema, but fail closed if legacy/broken data violates that assumption.
            user = None

        if user is None:
            # Match Django's timing-hardening behavior for unknown identities.
            user_model().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

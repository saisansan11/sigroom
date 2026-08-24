from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from accounts.models import Unit
from resources.models import Blackout, Resource, ResourceApprover, ResourceRule

from .context import request_ip
from .services import audit, model_snapshot


TRACKED_MODELS = (Resource, ResourceRule, ResourceApprover, Blackout, Unit, get_user_model())
UserModel = get_user_model()


def _clear_registry_state(instance):
    for attribute in ("_audit_skip_registry", "_audit_before", "_audit_password_changed"):
        if hasattr(instance, attribute):
            delattr(instance, attribute)


@receiver(pre_save)
def remember_before(sender, instance, update_fields=None, **kwargs):
    if sender not in TRACKED_MODELS or not instance.pk:
        return
    if sender is UserModel and update_fields and set(update_fields) <= {"last_login"}:
        instance._audit_skip_registry = True
        return
    try:
        previous = sender._default_manager.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    instance._audit_before = model_snapshot(previous)
    if sender is UserModel:
        instance._audit_password_changed = previous.password != instance.password


@receiver(post_save)
def registry_saved(sender, instance, created, raw=False, **kwargs):
    if raw or sender not in TRACKED_MODELS:
        return
    if getattr(instance, "_audit_skip_registry", False):
        _clear_registry_state(instance)
        return
    before = getattr(instance, "_audit_before", None)
    after = model_snapshot(instance)
    password_changed = bool(getattr(instance, "_audit_password_changed", False))
    if not created and before == after and not password_changed:
        _clear_registry_state(instance)
        return
    if password_changed:
        if before == after:
            before = {"password_changed": False}
            after = {"password_changed": True}
        else:
            after["password_changed"] = True
    audit(
        None,
        sender._meta.label_lower,
        instance.pk,
        "registry_created" if created else "registry_updated",
        before=before,
        after=after,
    )
    _clear_registry_state(instance)


@receiver(post_delete)
def registry_deleted(sender, instance, **kwargs):
    if sender in TRACKED_MODELS:
        audit(None, sender._meta.label_lower, instance.pk, "registry_deleted", before=model_snapshot(instance))


@receiver(m2m_changed, sender=Resource.custodians.through)
@receiver(m2m_changed, sender=ResourceRule.allowed_units.through)
@receiver(m2m_changed, sender=Blackout.rooms.through)
def registry_relation_changed(sender, instance, action, reverse, pk_set, **kwargs):
    if not action.startswith("post_"):
        return
    audit(
        None,
        instance._meta.label_lower,
        instance.pk,
        "registry_relation_changed",
        after={"operation": action.removeprefix("post_"), "reverse": reverse, "related_ids": sorted(str(item) for item in (pk_set or []))},
    )


@receiver(user_logged_in)
def logged_in(sender, request, user, **kwargs):
    audit(user, "accounts.user", user.pk, "login", ip=request_ip(request))


@receiver(user_logged_out)
def logged_out(sender, request, user, **kwargs):
    if user:
        audit(user, "accounts.user", user.pk, "logout", ip=request_ip(request))


@receiver(user_login_failed)
def login_failed(sender, credentials, request, **kwargs):
    username = credentials.get("username") or credentials.get("email") or ""
    audit(None, "accounts.user", username, "login_failed", after={"username": username}, ip=request_ip(request))

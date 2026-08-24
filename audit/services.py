from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from django.db import models

from .context import current_actor, current_ip
from .models import AuditLog


AUDIT_EXCLUDED_FIELDS = {"password", "last_login"}


def _json_value(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {
            str(key): _json_value(item)
            for key, item in value.items()
            if str(key) not in AUDIT_EXCLUDED_FIELDS
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_value(item) for item in value]
    return value


def model_snapshot(instance) -> dict:
    result = {}
    for field in instance._meta.concrete_fields:
        if field.name in AUDIT_EXCLUDED_FIELDS:
            continue
        value = getattr(instance, field.attname)
        result[field.name] = _json_value(value)
    return result


def audit(actor, entity, entity_id, action, before=None, after=None, ip="") -> AuditLog:
    actor = actor if getattr(actor, "is_authenticated", False) else current_actor()
    return AuditLog.objects.create(
        actor=actor,
        entity=str(entity)[:100],
        entity_id=str(entity_id or "")[:100],
        action=str(action)[:100],
        before=_json_value(before),
        after=_json_value(after),
        ip=(ip or current_ip())[:45],
    )

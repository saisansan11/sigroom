from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class AppendOnlyQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Audit log เป็นข้อมูล append-only ห้ามแก้ไข")

    def delete(self):
        raise ValidationError("Audit log เป็นข้อมูล append-only ห้ามลบ")


class AuditLog(models.Model):
    at = models.DateTimeField("เวลา", auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ผู้กระทำ",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    entity = models.CharField("ชนิดข้อมูล", max_length=100, db_index=True)
    entity_id = models.CharField("รหัสข้อมูล", max_length=100, blank=True, db_index=True)
    action = models.CharField("เหตุการณ์", max_length=100, db_index=True)
    before = models.JSONField("ก่อนเปลี่ยน", null=True, blank=True)
    after = models.JSONField("หลังเปลี่ยน", null=True, blank=True)
    ip = models.CharField("IP", max_length=45, blank=True)

    objects = AppendOnlyQuerySet.as_manager()

    class Meta:
        verbose_name = "Audit log"
        verbose_name_plural = "Audit log"
        ordering = ["-at", "-pk"]
        indexes = [models.Index(fields=["entity", "entity_id", "at"])]

    def save(self, *args, **kwargs):
        if self.pk is not None and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Audit log เป็นข้อมูล append-only ห้ามแก้ไข")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Audit log เป็นข้อมูล append-only ห้ามลบ")

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M:%S} {self.action} {self.entity}:{self.entity_id}"


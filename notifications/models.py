from django.conf import settings
from django.db import models


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ผู้รับ",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    text = models.CharField("ข้อความ", max_length=300)
    url = models.CharField("ลิงก์", max_length=200, blank=True)
    booking = models.ForeignKey(
        "bookings.Booking",
        verbose_name="การจอง",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
    )
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)
    read_at = models.DateTimeField("อ่านเมื่อ", null=True, blank=True)

    class Meta:
        verbose_name = "การแจ้งเตือน"
        verbose_name_plural = "การแจ้งเตือน"
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self):
        return f"{self.user}: {self.text}"

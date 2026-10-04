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
    kind = models.CharField(
        "ชนิดการแจ้งเตือน",
        max_length=30,
        blank=True,
        default="",
        db_default="",
    )
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
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "user", "kind"],
                condition=~models.Q(kind=""),
                name="uniq_notification_booking_user_kind",
            ),
        ]

    def __str__(self):
        return f"{self.user}: {self.text}"


class PushSubscription(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="ผู้รับ", on_delete=models.CASCADE,
        related_name="push_subscriptions",
    )
    endpoint = models.URLField("ปลายทางแจ้งเตือน", max_length=2048, unique=True)
    p256dh = models.CharField("กุญแจเข้ารหัสจากเบราว์เซอร์", max_length=100)
    auth = models.CharField("กุญแจยืนยันจากเบราว์เซอร์", max_length=30)
    user_agent = models.CharField("เบราว์เซอร์", max_length=500, blank=True)
    created_at = models.DateTimeField("ลงทะเบียนเมื่อ", auto_now_add=True)
    last_success_at = models.DateTimeField("ส่งสำเร็จล่าสุด", null=True, blank=True)
    failed_count = models.PositiveIntegerField("จำนวนครั้งที่ส่งไม่สำเร็จ", default=0)

    class Meta:
        verbose_name = "เครื่องรับแจ้งเตือน"
        verbose_name_plural = "เครื่องรับแจ้งเตือน"
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return f"เครื่องรับแจ้งเตือน #{self.pk}"

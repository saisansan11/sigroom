from django.conf import settings
from django.db import models


class Approval(models.Model):
    class Action(models.TextChoices):
        SUBMITTED = "submitted", "ส่งคำขอ"
        APPROVED = "approved", "อนุมัติ"
        REJECTED = "rejected", "ปฏิเสธ"
        EXPIRED = "expired", "หมดอายุ"

    booking = models.ForeignKey(
        "bookings.Booking",
        verbose_name="การจอง",
        on_delete=models.PROTECT,
        related_name="approvals",
    )
    action = models.CharField("การพิจารณา", max_length=20, choices=Action.choices)
    acted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ดำเนินการโดย",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approval_actions",
    )
    on_behalf_of = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="รักษาการแทน",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="approval_actions_on_behalf",
    )
    reason = models.TextField("เหตุผล", blank=True)
    acted_at = models.DateTimeField("ดำเนินการเมื่อ", auto_now_add=True)

    class Meta:
        verbose_name = "ประวัติการพิจารณา"
        verbose_name_plural = "ประวัติการพิจารณา"
        ordering = ["acted_at", "pk"]
        indexes = [models.Index(fields=["booking", "acted_at"])]

    def __str__(self):
        return f"{self.booking_id} — {self.get_action_display()}"


class ApproverDelegation(models.Model):
    delegator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ผู้มอบหมาย",
        on_delete=models.PROTECT,
        related_name="delegations_given",
    )
    delegate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ผู้รักษาการ",
        on_delete=models.PROTECT,
        related_name="delegations_received",
    )
    start_date = models.DateField("ตั้งแต่วันที่")
    end_date = models.DateField("ถึงวันที่")
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)

    class Meta:
        verbose_name = "ผู้รักษาการแทน"
        verbose_name_plural = "ผู้รักษาการแทน"
        ordering = ["-start_date", "-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="delegation_end_on_or_after_start",
            ),
            models.CheckConstraint(
                condition=~models.Q(delegator=models.F("delegate")),
                name="delegation_different_users",
            ),
        ]

    def __str__(self):
        return f"{self.delegator} → {self.delegate} ({self.start_date}–{self.end_date})"

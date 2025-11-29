# log/models.py
"""Models for logging events related to orders and vouchers."""
from django.db import models
from django.contrib.auth.models import User  # Import the User model
from django.conf import settings  # Import the settings module


class EmailLog(models.Model):
    """Model to log sent emails and their statuses."""
    EMAIL_TYPE_CHOICES = [
        ("onboarding", "Onboarding"),
        ("password_reset", "Password Reset"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email_type = models.CharField(max_length=50, choices=EMAIL_TYPE_CHOICES)
    sent_at = models.DateTimeField(auto_now_add=True)
    message_id = models.CharField(max_length=255, blank=True, null=True)
    unique_together = ("user", "email_type")

    class Meta:
        app_label = 'log'


class BaseLog(models.Model):
    """Abstract base log model for tracking events related to orders and vouchers."""
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'

    LOG_TYPE_CHOICES = [
        (INFO, 'Info'),
        (WARNING, 'Warning'),
        (ERROR, 'Error'),
    ]

    participant = models.ForeignKey(
        "account.Participant",
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    message = models.TextField()
    log_type = models.CharField(
        max_length=10, choices=LOG_TYPE_CHOICES, default=INFO
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta options for the log model."""
        abstract = True
        ordering = ["-created_at"]

    def __str__(self):
        target = f"Order {self.order_id}" if self.order_id else "General"
        return f"{target} [{self.log_type}]: {self.message[:50]}"


class VoucherLog(BaseLog):
    """
    Log model for tracking voucher-related events.
    """
    voucher = models.ForeignKey(
        "voucher.Voucher",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="logs"
    )
    balance_before = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    balance_after = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    applied_amount = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    remaining = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    validated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.voucher_id:
            target = f"Voucher {self.voucher_id}"
        else:
            target = super().__str__()
        return (
            f"{target} [{self.log_type}]: "
            f"{str(self.message)[:50]}"
        )


class OrderValidationLog(BaseLog):
    """Log model for tracking order validation errors."""
    product = models.ForeignKey(
        "pantry.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    validated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.validated_at} — {self.participant or 'Unknown'}: "
            f"{self.message}"
        )


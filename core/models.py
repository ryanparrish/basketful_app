"""Core application models."""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class OrderWindowSettings(models.Model):
    """
    Singleton model for controlling when participants can place orders.
    Only one instance should exist.
    """
    hours_before_class = models.PositiveIntegerField(
        default=24,
        validators=[MinValueValidator(1), MaxValueValidator(168)],
        help_text=(
            "Hours before class time when ordering window opens "
            "(1-168 hours, default 24)"
        )
    )
    
    hours_before_close = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(168)],
        help_text=(
            "Hours before class time when ordering window closes "
            "(0-168 hours, default 0 = closes at class time)"
        )
    )
    
    enabled = models.BooleanField(
        default=True,
        help_text="Enable/disable order window restrictions"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Order Window Setting"
        verbose_name_plural = "Order Window Settings"
    
    def __str__(self):
        status = "Enabled" if self.enabled else "Disabled"
        return (
            f"Order Window: {self.hours_before_class}h "
            f"before class ({status})"
        )
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        if not self.pk and OrderWindowSettings.objects.exists():
            # Update existing instance instead of creating new one
            existing = OrderWindowSettings.objects.first()
            existing.hours_before_class = self.hours_before_class
            existing.enabled = self.enabled
            existing.save()
            return existing
        return super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={'hours_before_class': 24, 'enabled': True}
        )
        return obj

"""Core application models."""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings


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


class EmailSettings(models.Model):
    """
    Singleton model for global email configuration.
    Provides default from_email and reply_to addresses.
    """
    from_email_default = models.EmailField(
        blank=True,
        help_text=(
            "Default from email address. Leave blank to use Django's "
            "DEFAULT_FROM_EMAIL setting."
        )
    )
    reply_to_default = models.EmailField(
        default="it@loveyourneighbor.org",
        help_text="Default reply-to email address for all emails"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Email Setting"
        verbose_name_plural = "Email Settings"
    
    def __str__(self):
        return "Email Settings"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        if not self.pk and EmailSettings.objects.exists():
            # Update existing instance instead of creating new one
            existing = EmailSettings.objects.first()
            existing.from_email_default = self.from_email_default
            existing.reply_to_default = self.reply_to_default
            existing.save()
            return existing
        return super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={'reply_to_default': 'it@loveyourneighbor.org'}
        )
        return obj
    
    def get_from_email(self):
        """Get the from email address, falling back to Django setting."""
        if self.from_email_default:
            return self.from_email_default
        return getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    
    def get_reply_to(self):
        """Get the default reply-to address."""
        return self.reply_to_default

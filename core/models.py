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


class BrandingSettings(models.Model):
    """Singleton model for organization branding configuration."""
    organization_name = models.CharField(
        max_length=255,
        default="Love Your Neighbor",
        help_text="Organization name to display on printed orders"
    )
    logo = models.ImageField(
        upload_to='branding/',
        blank=True,
        null=True,
        help_text="Upload organization logo (displayed on printed orders)"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Branding Setting"
        verbose_name_plural = "Branding Settings"
    
    def __str__(self):
        return "Branding Settings"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        if not self.pk and BrandingSettings.objects.exists():
            existing = BrandingSettings.objects.first()
            existing.organization_name = self.organization_name
            existing.logo = self.logo
            existing.save()
            return existing
        return super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={'organization_name': 'Love Your Neighbor'}
        )
        return obj


class ProgramSettings(models.Model):
    """Singleton model for program-wide settings including grace allowance."""
    grace_amount = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.00,
        validators=[MinValueValidator(0.00), MaxValueValidator(100.00)],
        help_text="Dollar amount over budget allowed as 'grace' for financial literacy learning (default $1.00)"
    )
    grace_enabled = models.BooleanField(
        default=True,
        help_text="Enable/disable grace allowance feature"
    )
    grace_message = models.TextField(
        default="This helps you practice staying within budget",
        help_text="Educational message displayed when user is within grace allowance"
    )
    rules_version = models.CharField(
        max_length=32,
        blank=True,
        editable=False,
        help_text="MD5 hash of business rules (auto-generated)"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Program Setting"
        verbose_name_plural = "Program Settings"
    
    def __str__(self):
        status = "Enabled" if self.grace_enabled else "Disabled"
        return f"Program Settings (Grace: ${self.grace_amount} - {status})"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        if not self.pk and ProgramSettings.objects.exists():
            existing = ProgramSettings.objects.first()
            existing.grace_amount = self.grace_amount
            existing.grace_enabled = self.grace_enabled
            existing.grace_message = self.grace_message
            existing.save()
            return existing
        return super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'grace_amount': 1.00,
                'grace_enabled': True,
                'grace_message': 'This helps you practice staying within budget'
            }
        )
        return obj


class ThemeSettings(models.Model):
    """Singleton model for participant frontend theme configuration."""
    primary_color = models.CharField(
        max_length=7,
        default="#1976d2",
        help_text="Primary theme color (hex format, e.g., #1976d2)"
    )
    secondary_color = models.CharField(
        max_length=7,
        default="#dc004e",
        help_text="Secondary theme color (hex format, e.g., #dc004e)"
    )
    app_name = models.CharField(
        max_length=100,
        default="Basketful",
        help_text="Application name displayed in participant frontend"
    )
    logo = models.ImageField(
        upload_to='theme/',
        blank=True,
        null=True,
        help_text="Logo displayed on participant login page"
    )
    favicon = models.ImageField(
        upload_to='theme/',
        blank=True,
        null=True,
        help_text="Favicon for participant frontend (32x32 or 16x16)"
    )
    
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Theme Setting"
        verbose_name_plural = "Theme Settings"
    
    def __str__(self):
        return f"Theme Settings ({self.app_name})"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)."""
        if not self.pk and ThemeSettings.objects.exists():
            existing = ThemeSettings.objects.first()
            existing.primary_color = self.primary_color
            existing.secondary_color = self.secondary_color
            existing.app_name = self.app_name
            existing.logo = self.logo
            existing.favicon = self.favicon
            existing.save()
            return existing
        return super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'primary_color': '#1976d2',
                'secondary_color': '#dc004e',
                'app_name': 'Basketful'
            }
        )
        return obj

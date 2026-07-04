"""Core application models."""
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings


class ProgramOrderWindow(models.Model):
    """
    Sparse per-program override for order window settings.

    Each field is nullable — null means "inherit from the global
    OrderWindowSettings singleton".  Only programs that need custom
    behaviour get a row here; all others fall through to the global
    defaults automatically via get_effective_config() in core/utils.py.

    3NF note: MeetingDay / meeting_time live on Program, never here.
    Derived state (current status, next open/close times) is computed
    at request time and never stored.
    """
    program = models.OneToOneField(
        'lifeskills.Program',
        on_delete=models.CASCADE,
        related_name='order_window',
    )
    hours_before_class = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(168)],
        help_text=(
            "Override: hours before class the window opens. "
            "Leave blank to use the global default."
        ),
    )
    hours_before_close = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(168)],
        help_text=(
            "Override: hours before class the window closes. "
            "Leave blank to use the global default."
        ),
    )
    enabled = models.BooleanField(
        null=True,
        blank=True,
        help_text=(
            "Override: enable/disable this program's order window. "
            "Leave blank to use the global default."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Program Order Window Override"
        verbose_name_plural = "Program Order Window Overrides"

    def __str__(self) -> str:
        return f"Order window override for {self.program.name}"


class ProgramWindowOverride(models.Model):
    """
    Manual force-open / force-close for a single program's order window.

    Staff can push a program into a forced state (e.g. force-close during
    an inventory audit) with an explicit expiry time.  The backend expires
    the record lazily on read; a Celery beat task also cleans up expired
    rows nightly.

    OneToOneField ensures only one active override per program at the DB
    level — replacing an override is an upsert, not an append.
    """
    FORCE_STATUS_CHOICES = [
        ('open', 'Force Open'),
        ('closed', 'Force Closed'),
    ]

    program = models.OneToOneField(
        'lifeskills.Program',
        on_delete=models.CASCADE,
        related_name='window_override',
    )
    force_status = models.CharField(
        max_length=10,
        choices=FORCE_STATUS_CHOICES,
    )
    expires_at = models.DateTimeField(
        help_text="Override is automatically ignored after this time.",
    )
    reason = models.TextField(
        blank=True,
        help_text="Why is this override active? Shown to other staff.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='window_overrides_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Program Window Override"
        verbose_name_plural = "Program Window Overrides"

    def __str__(self) -> str:
        return (
            f"Force-{self.force_status} override for {self.program.name} "
            f"until {self.expires_at:%Y-%m-%d %H:%M}"
        )

    def is_active(self) -> bool:
        """Return True if the override has not yet expired."""
        from django.utils import timezone
        return self.expires_at > timezone.now()


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
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
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
            # Copy the modeltranslation language columns too, or the
            # singleton merge would silently drop translations
            from django.conf import settings as django_settings
            for language_code, _label in django_settings.LANGUAGES:
                field = f'grace_message_{language_code}'
                if hasattr(self, field):
                    setattr(existing, field, getattr(self, field))
            existing.save()
            return existing
        return super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the singleton settings instance."""
        obj, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'grace_amount': Decimal('1.00'),
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

# log/models.py
"""Models for logging events related to orders and vouchers."""
from django.db import models
from django.contrib.auth.models import User  # Import the User model
from django.conf import settings  # Import the settings module
from django.template import Template, Context
from django.template.loader import render_to_string
from tinymce.models import HTMLField


class EmailType(models.Model):
    """
    Model for managing email types with configurable templates and settings.
    Allows admins to edit email content directly in Django admin.
    """
    name = models.SlugField(
        max_length=100,
        unique=True,
        help_text="Internal identifier (e.g., 'onboarding', 'password_reset')"
    )
    display_name = models.CharField(
        max_length=255,
        help_text="Human-readable name (e.g., 'New User Onboarding')"
    )
    subject = models.CharField(
        max_length=255,
        help_text="Email subject line (supports template variables like {{ user.first_name }})"
    )
    
    # Template file paths (fallback)
    html_template = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path to HTML template file (e.g., 'registration/new_user_onboarding.html')"
    )
    text_template = models.CharField(
        max_length=255,
        blank=True,
        help_text="Path to text template file (e.g., 'registration/new_user_onboarding.txt')"
    )
    
    # Editable content (takes priority over template files)
    html_content = HTMLField(
        blank=True,
        help_text="HTML email content (editable). Takes priority over template file."
    )
    text_content = models.TextField(
        blank=True,
        help_text="Plain text email content. Takes priority over template file."
    )
    
    # Email addresses
    from_email = models.EmailField(
        blank=True,
        help_text="From email address (leave blank to use global default)"
    )
    reply_to = models.EmailField(
        blank=True,
        help_text="Reply-to email address (leave blank to use global default)"
    )
    
    # Documentation
    available_variables = models.TextField(
        blank=True,
        help_text="Documentation of available template variables for this email type"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of when this email is sent and its purpose"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Enable/disable sending of this email type"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Email Type"
        verbose_name_plural = "Email Types"
        ordering = ['display_name']
    
    def __str__(self):
        status = "✓" if self.is_active else "✗"
        return f"{status} {self.display_name}"
    
    def render_subject(self, context_dict):
        """Render the subject line with the given context."""
        template = Template(self.subject)
        return template.render(Context(context_dict))
    
    def render_html(self, context_dict):
        """
        Render HTML content. Uses html_content if set, otherwise falls back
        to html_template file.
        """
        if self.html_content:
            template = Template(self.html_content)
            return template.render(Context(context_dict))
        elif self.html_template:
            return render_to_string(self.html_template, context_dict)
        return ""
    
    def render_text(self, context_dict):
        """
        Render text content. Uses text_content if set, otherwise falls back
        to text_template file.
        """
        if self.text_content:
            template = Template(self.text_content)
            return template.render(Context(context_dict))
        elif self.text_template:
            return render_to_string(self.text_template, context_dict)
        return ""
    
    @classmethod
    def get_sample_context(cls):
        """
        Returns sample context data for email preview.
        """
        return {
            'user': type('SampleUser', (), {
                'first_name': 'John',
                'last_name': 'Doe',
                'username': 'john_doe',
                'email': 'john.doe@example.com',
                'get_username': lambda self: 'john_doe',
            })(),
            'domain': 'example.com',
            'protocol': 'https',
            'uid': 'sample-uid-123',
            'token': 'sample-token-abc',
            'site_name': 'Basketful',
        }


class EmailLog(models.Model):
    """Model to log sent emails and their statuses."""
    STATUS_CHOICES = [
        ("sent", "Sent"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email_type = models.ForeignKey(
        EmailType,
        on_delete=models.PROTECT,
        related_name='logs',
        help_text="The type of email that was sent"
    )
    subject = models.CharField(
        max_length=255,
        blank=True,
        help_text="The rendered subject at time of sending"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="sent"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Error details if the email failed to send"
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    message_id = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        app_label = 'log'
        ordering = ['-sent_at']
        verbose_name = "Email Log"
        verbose_name_plural = "Email Logs"
    
    def __str__(self):
        return f"{self.email_type.display_name} to {self.user.email} ({self.status})"


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


class UserLoginLog(models.Model):
    """Track user login and logout activity."""
    LOGIN = 'login'
    LOGOUT = 'logout'
    FAILED_LOGIN = 'failed_login'
    
    ACTION_CHOICES = [
        (LOGIN, 'Login'),
        (LOGOUT, 'Logout'),
        (FAILED_LOGIN, 'Failed Login'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='login_logs',
        null=True,
        blank=True
    )
    username_attempted = models.CharField(
        max_length=150,
        blank=True,
        help_text="Username used in login attempt (for failed logins)"
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_CHOICES
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    participant = models.ForeignKey(
        'account.Participant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_logs'
    )
    
    class Meta:
        app_label = 'log'
        ordering = ['-timestamp']
        verbose_name = "User Login Log"
        verbose_name_plural = "User Login Logs"
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]
    
    def __str__(self):
        user_display = self.user.username if self.user else self.username_attempted
        return f"{user_display} - {self.get_action_display()} at {self.timestamp}"


class GraceAllowanceLog(models.Model):
    """
    Log entries for when participants use the grace allowance feature.
    Used to track financial literacy learning moments and for admin notifications.
    """
    participant = models.ForeignKey(
        'account.Participant',
        on_delete=models.CASCADE,
        related_name='grace_logs',
        help_text="Participant who used grace allowance"
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grace_logs',
        help_text="Order associated with grace allowance usage"
    )
    amount_over = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Dollar amount over budget"
    )
    grace_message = models.TextField(
        help_text="Educational message displayed to participant"
    )
    proceeded = models.BooleanField(
        default=False,
        help_text="Whether participant proceeded with order after grace warning"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'log'
        ordering = ['-created_at']
        verbose_name = "Grace Allowance Log"
        verbose_name_plural = "Grace Allowance Logs"
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['participant', '-created_at']),
        ]
    
    def __str__(self):
        action = "proceeded" if self.proceeded else "reviewed"
        return f"{self.participant} - ${self.amount_over} over ({action}) at {self.created_at}"

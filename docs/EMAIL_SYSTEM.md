# Email System

> Last updated: January 2026

## Overview
The Basketful email system provides a flexible, admin-configurable approach to managing transactional emails. Administrators can edit email templates directly from Django Admin without requiring code deployments.

## Features

### Admin-Editable Templates
- **TinyMCE Editor**: Rich text editor for HTML emails
- **Plain Text**: Alternative plain text content
- **Template Variables**: Django template syntax support
- **Live Preview**: See rendered emails before saving

### Email Types
Configurable email types include:
- **Onboarding** - New user welcome emails
- **Password Reset** - Password reset instructions
- **Order Confirmation** - Order placed notifications
- **Voucher Created** - Voucher availability notifications

### Flexible Configuration
- **Database or Files**: Content can be in database or template files
- **Priority System**: Database content overrides template files
- **Global Defaults**: Fallback email addresses
- **Enable/Disable**: Toggle email types on/off

## Model: EmailType

### Fields

**Identification**
- `name` - Slug identifier (e.g., 'onboarding', 'password_reset')
- `display_name` - Human-readable name
- `is_active` - Enable/disable sending

**Subject & Content**
- `subject` - Email subject with template variable support
- `html_content` - Rich HTML content (editable in admin)
- `text_content` - Plain text alternative
- `html_template` - Fallback template file path
- `text_template` - Fallback text template path

**Email Configuration**
- `from_email` - Override default from address
- `reply_to` - Override default reply-to address

**Documentation**
- `available_variables` - Docs for template variables
- `description` - When email is sent and purpose

### Template Variables

Common variables available in all emails:
```python
{
    'user': User object,
    'participant': Participant object (if applicable),
    'site_name': 'Basketful',
    'site_url': 'https://basketful.lovewm.org',
}
```

Email-specific variables:
```python
# Onboarding
{
    'username': 'john_doe',
    'password': 'temporary_password',
    'login_url': 'https://...',
}

# Order Confirmation
{
    'order': Order object,
    'order_number': 'ORD-20260117-000123',
    'items': QuerySet of OrderItem,
    'total': Decimal('45.50'),
}
```

## Admin Interface

### Location
**Admin → Log → Email Types**

### Features

#### Rich Text Editor
- TinyMCE integration for HTML content
- Toolbar: Bold, italic, links, images, tables
- Code view for advanced editing

#### Live Preview
- Preview button renders email with sample data
- Shows subject, HTML, and text versions
- Modal popup display

#### Indicators
- ✓ Database - Content stored in database
- 📄 File - Using template file
- — - No content configured

#### Fieldsets
1. **Basic Information** - Name, display name, active status
2. **Email Content** - Editable HTML and text content
3. **Fallback Templates** - Template file paths
4. **Email Addresses** - From/reply-to overrides
5. **Documentation** - Variable docs and description
6. **Metadata** - Created/updated timestamps

## Usage

### Creating a New Email Type

1. Navigate to **Admin → Log → Email Types**
2. Click **"Add Email Type"**
3. Fill in fields:
   - **Name**: `order_confirmation` (slug format)
   - **Display Name**: `Order Confirmation`
   - **Subject**: `Your order #{{ order.order_number }} has been placed`
   - **HTML Content**: Use TinyMCE editor
   - **Text Content**: Plain text version
   - **Available Variables**: Document `{{ order }}`, `{{ items }}`, etc.
4. Click **Preview** to test rendering
5. Save

### Editing Existing Templates

1. Find email type in list
2. Click to edit
3. Modify HTML/text content
4. Use **Preview** button to verify
5. Save changes
6. No code deployment needed!

### Sending Emails

Emails are sent via utility functions:
```python
from apps.log.models import EmailType

def send_onboarding_email(user, password):
    email_type = EmailType.objects.get(name='onboarding')
    
    if not email_type.is_active:
        return  # Email type disabled
    
    context = {
        'user': user,
        'username': user.username,
        'password': password,
        'login_url': 'https://basketful.lovewm.org/login/',
    }
    
    subject = email_type.render_subject(context)
    html = email_type.render_html(context)
    text = email_type.render_text(context)
    
    send_mail(
        subject=subject,
        message=text,
        from_email=email_type.from_email or settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html,
    )
```

## Model: EmailLog

### Purpose
Track all emails sent for audit purposes.

### Fields
- `email_type` - ForeignKey to EmailType
- `recipient` - Email address
- `subject` - Rendered subject
- `sent_at` - Timestamp
- `status` - Success/failure
- `error_message` - If failed
- `user` - Associated user (optional)
- `participant` - Associated participant (optional)

### Admin
View email history at **Admin → Log → Email Logs**

## Technical Implementation

### Files
- **apps/log/models.py** - EmailType and EmailLog models
- **apps/log/admin.py** - Admin interface with preview
- **apps/log/templates/admin/log/emailtype/change_form.html** - Custom admin template
- **apps/account/tasks/email.py** - Email sending tasks

### Rendering Methods

```python
class EmailType(models.Model):
    def render_subject(self, context_dict):
        """Render subject with context."""
        template = Template(self.subject)
        return template.render(Context(context_dict))
    
    def render_html(self, context_dict):
        """Render HTML content or fallback to file."""
        if self.html_content:
            template = Template(self.html_content)
            return template.render(Context(context_dict))
        elif self.html_template:
            return render_to_string(self.html_template, context_dict)
        return ""
    
    def render_text(self, context_dict):
        """Render text content or fallback to file."""
        if self.text_content:
            template = Template(self.text_content)
            return template.render(Context(context_dict))
        elif self.text_template:
            return render_to_string(self.text_template, context_dict)
        return ""
```

### Preview API

```python
@admin.register(EmailType)
class EmailTypeAdmin(admin.ModelAdmin):
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/preview/',
                self.admin_site.admin_view(self.preview_view),
                name='emailtype-preview',
            ),
        ]
        return custom_urls + urls
    
    def preview_view(self, request, pk):
        """Return rendered email preview as JSON."""
        email_type = EmailType.objects.get(pk=pk)
        context = EmailType.get_sample_context()
        
        return JsonResponse({
            'subject': email_type.render_subject(context),
            'html': email_type.render_html(context),
            'text': email_type.render_text(context),
        })
```

## Benefits

### For Administrators
- ✅ Edit emails without code changes
- ✅ Preview before sending
- ✅ Quick updates to messaging
- ✅ No developer dependency

### For Developers
- ✅ Centralized email management
- ✅ Consistent template variables
- ✅ Audit logging built-in
- ✅ Easy to add new email types

### For Users
- ✅ Professional branded emails
- ✅ HTML and plain text versions
- ✅ Consistent messaging
- ✅ Reliable delivery

## Future Enhancements

- Email scheduling/queuing
- A/B testing support
- Email analytics (opens, clicks)
- Attachment support
- Multi-language templates
- Bulk email sending

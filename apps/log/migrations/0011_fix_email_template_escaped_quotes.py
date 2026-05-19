"""
Migration: Fix escaped single quotes in EmailType template content.

TinyMCE (now replaced with Monaco) stored Django template tags with
backslash-escaped quotes — e.g. {%  url \'password_reset_confirm\' %}
instead of {% url 'password_reset_confirm' %}. This caused
TemplateSyntaxError in every Celery email task.

This migration restores clean content for both the password_reset and
onboarding EmailType records.
"""
from django.db import migrations


PASSWORD_RESET_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Your Password</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f7fa; color: #374151; padding: 20px; margin: 0; line-height: 1.6; }
        .container { background: #ffffff; border-radius: 12px; padding: 40px; max-width: 560px; margin: 20px auto; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
        .header { text-align: center; margin-bottom: 30px; }
        .logo { font-size: 28px; margin-bottom: 8px; color: #3b82f6; font-weight: bold; }
        h2 { color: #1f2937; font-size: 24px; font-weight: 600; margin: 0 0 8px 0; }
        .subtitle { color: #6b7280; font-size: 16px; margin: 0; }
        .content { margin: 30px 0; }
        .content p { color: #4b5563; font-size: 16px; margin: 0 0 16px 0; }
        .btn-container { text-align: center; margin: 32px 0; }
        .btn { display: inline-block; background-color: #3b82f6; color: #ffffff !important; padding: 14px 32px; border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 16px; }
        .btn:hover { background-color: #2563eb; }
        .info-box { background: #f9fafb; border-radius: 8px; padding: 20px 24px; margin: 24px 0; border-left: 4px solid #3b82f6; }
        .info-box p { margin: 0; color: #374151; font-size: 14px; }
        .footer { border-top: 1px solid #e5e7eb; padding-top: 24px; margin-top: 32px; }
        .footer p { color: #9ca3af; font-size: 14px; margin: 0 0 12px 0; }
        .signature { color: #6b7280; font-size: 15px; }
        .signature strong { color: #374151; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">Basketful</div>
            <h2>Reset Your Password</h2>
            <p class="subtitle">Love Your Neighbor Life Skills Program</p>
        </div>
        <div class="content">
            <p>Hello {{ user.get_username }},</p>
            <p>You're receiving this email because you requested a password reset for your account.</p>
        </div>
        <div class="btn-container">
            <a href="{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}" class="btn">Reset Your Password</a>
        </div>
        <div class="info-box">
            <p>This link will expire after use. If you didn't request a password reset, you can safely ignore this email.</p>
        </div>
        <div class="footer">
            <p>If the button above doesn't work, copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #3b82f6;">{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}</p>
            <p class="signature">Thanks,<br><strong>The Basketful Team</strong></p>
        </div>
    </div>
</body>
</html>"""

PASSWORD_RESET_TEXT = """Hello {{ user.get_username }},

You're receiving this email because you requested a password reset for your user account at {{ site_name }}.

Please go to the following page and choose a new password:

{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}

If you didn't request a password reset, you can ignore this email.

Thanks,
{{ site_name }} team"""

ONBOARDING_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; }
        .header { background: #2d6a4f; color: white; padding: 30px; text-align: center; }
        .header .logo { font-size: 36px; margin-bottom: 10px; }
        .header h2 { margin: 0 0 5px 0; font-size: 24px; }
        .header .subtitle { margin: 0; opacity: 0.9; font-size: 14px; }
        .content { padding: 20px 30px; color: #333; }
        .login-box { background: #f0f7f4; border: 2px solid #2d6a4f; border-radius: 8px; padding: 20px 30px; margin: 20px 0; text-align: center; }
        .login-box .login-label { font-size: 12px; font-weight: bold; letter-spacing: 1px; color: #555; text-transform: uppercase; margin: 0 0 8px 0; }
        .login-box .login-value { font-size: 32px; font-weight: 900; letter-spacing: 4px; color: #1a3c2a; font-family: monospace; margin: 0 0 8px 0; }
        .login-box .login-note { margin: 0; font-size: 13px; color: #555; }
        .btn-container { text-align: center; margin: 20px 0; }
        .btn { background: #2d6a4f; color: white; padding: 12px 28px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block; }
        .login-url { background: #f5f5f5; border-radius: 6px; padding: 12px 20px; margin: 16px 0; }
        .login-url p { margin: 0; font-size: 14px; color: #333; }
        .login-url a { color: #2d6a4f; font-weight: bold; }
        .checklist { padding: 10px 30px; color: #555; font-size: 14px; }
        .checklist p { margin: 4px 0; }
        .footer { background: #f5f5f5; padding: 20px 30px; text-align: center; font-size: 12px; color: #888; }
        .signature { margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">Basketful</div>
            <h2>Welcome, {{ user.first_name|default:"Friend" }}!</h2>
            <p class="subtitle">Love Your Neighbor Life Skills Program</p>
        </div>
        <div class="content">
            <p>We're excited to have you join our community! Your Basketful account has been created where you'll place and manage your food orders.</p>
        </div>
        <div class="login-box">
            <p class="login-label">Your Login Number</p>
            <p class="login-value">{{ participant_customer_number }}</p>
            <p class="login-note">Save this — you'll type it in every time you log in.</p>
        </div>
        <div class="content">
            <p><strong>Step 1</strong> — Set your password by clicking the button below:</p>
        </div>
        <div class="btn-container">
            <a href="{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}" class="btn">Set Your Password</a>
        </div>
        <div class="content">
            <p><em>This link expires in 3 days. If it has expired, ask pantry staff to resend.</em></p>
        </div>
        <div class="login-url">
            <p><strong>Step 2</strong> — Log in at: <a href="{{ participant_frontend_url }}/login">{{ participant_frontend_url }}/login</a></p>
        </div>
        <div class="checklist">
            <p>Set your password</p>
            <p>Log in with your login number</p>
            <p>Place your food orders</p>
        </div>
        <div class="footer">
            <p>If you didn't request this account or believe this was sent in error, you can safely ignore this email.</p>
            <p class="signature">Thanks,<br><strong>The Basketful Team</strong></p>
        </div>
    </div>
</body>
</html>"""

ONBOARDING_TEXT = """Welcome to Basketful, {{ user.first_name|default:"Friend" }}!

Love Your Neighbor Life Skills Program

We're excited to have you join our community!

========================================
YOUR LOGIN NUMBER: {{ participant_customer_number }}
========================================
Keep this — you'll type it in every time you log in.

Step 1 — Set your password:
{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}

This link expires in 3 days. If it has expired, ask pantry staff to resend.

Step 2 — Log in at:
{{ participant_frontend_url }}/login

Step 3 — Place your first order!

Questions? Reply to this email or speak to your pantry coordinator.

— The Basketful Team
"""


def fix_email_templates(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')

    try:
        pr = EmailType.objects.get(name='password_reset')
        pr.html_content = PASSWORD_RESET_HTML
        pr.text_content = PASSWORD_RESET_TEXT
        pr.save()
    except EmailType.DoesNotExist:
        pass

    try:
        onboarding = EmailType.objects.get(name='onboarding')
        onboarding.html_content = ONBOARDING_HTML
        onboarding.text_content = ONBOARDING_TEXT
        onboarding.save()
    except EmailType.DoesNotExist:
        pass


def reverse_fix(apps, schema_editor):
    pass  # One-way fix; no value in restoring broken content


class Migration(migrations.Migration):

    dependencies = [
        ('log', '0010_fix_onboarding_email_customer_number'),
    ]

    operations = [
        migrations.RunPython(fix_email_templates, reverse_fix),
    ]

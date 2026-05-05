"""
Migration: Fix onboarding email to show customer number, not username.

Participants log in with their customer number (C-BKM-7), not their Django
username (jane-smith-hope). This migration updates the onboarding EmailType
record to show the correct credential and adds the login URL.

New template variables exposed:
  {{ participant_customer_number }}  — e.g. "C-BKM-7"
  {{ participant_frontend_url }}     — e.g. "https://app.basketful.org"

These are injected by send_new_user_onboarding_email() in tasks/email.py.
"""
from django.db import migrations


NEW_HTML_CONTENT = '''<!DOCTYPE html>
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
        .login-box {
            background: #f0f7f4;
            border: 2px solid #2d6a4f;
            border-radius: 8px;
            padding: 20px 30px;
            margin: 20px 0;
            text-align: center;
        }
        .login-box .login-label {
            font-size: 12px;
            font-weight: bold;
            letter-spacing: 1px;
            color: #555;
            text-transform: uppercase;
            margin: 0 0 8px 0;
        }
        .login-box .login-value {
            font-size: 32px;
            font-weight: 900;
            letter-spacing: 4px;
            color: #1a3c2a;
            font-family: monospace;
            margin: 0 0 8px 0;
        }
        .login-box .login-note { margin: 0; font-size: 13px; color: #555; }
        .btn-container { text-align: center; margin: 20px 0; }
        .btn {
            background: #2d6a4f;
            color: white;
            padding: 12px 28px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: bold;
            display: inline-block;
        }
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
            <div class="logo">🥕 Basketful</div>
            <h2>Welcome, {{ user.first_name|default:"Friend" }}!</h2>
            <p class="subtitle">Love Your Neighbor Life Skills Program</p>
        </div>
        <div class="content">
            <p>We\'re excited to have you join our community! Your Basketful account has been created where you\'ll place and manage your food orders.</p>
        </div>
        <div class="login-box">
            <p class="login-label">Your Login Number</p>
            <p class="login-value">{{ participant_customer_number }}</p>
            <p class="login-note">📝 Save this — you\'ll type it in every time you log in.</p>
        </div>
        <div class="content">
            <p><strong>Step 1</strong> — Set your password by clicking the button below:</p>
        </div>
        <div class="btn-container">
            <a href="{{ protocol }}://{{ domain }}{% url \'password_reset_confirm\' uidb64=uid token=token %}" class="btn">Set Your Password</a>
        </div>
        <div class="content">
            <p><em>This link expires in 3 days. If it has expired, ask pantry staff to resend.</em></p>
        </div>
        <div class="login-url">
            <p><strong>Step 2</strong> — Log in at: <a href="{{ participant_frontend_url }}/login">{{ participant_frontend_url }}/login</a></p>
        </div>
        <div class="checklist">
            <p>✓ Set your password</p>
            <p>✓ Log in with your login number</p>
            <p>✓ Place your food orders</p>
        </div>
        <div class="footer">
            <p>If you didn\'t request this account or believe this was sent in error, you can safely ignore this email.</p>
            <p class="signature">Thanks,<br><strong>The Basketful Team</strong></p>
        </div>
    </div>
</body>
</html>'''

NEW_TEXT_CONTENT = '''Welcome to Basketful, {{ user.first_name|default:"Friend" }}!

Love Your Neighbor Life Skills Program

We\'re excited to have you join our community!

========================================
YOUR LOGIN NUMBER: {{ participant_customer_number }}
========================================
Keep this — you\'ll type it in every time you log in.

Step 1 — Set your password:
{{ protocol }}://{{ domain }}{% url \'password_reset_confirm\' uidb64=uid token=token %}

This link expires in 3 days. If it has expired, ask pantry staff to resend.

Step 2 — Log in at:
{{ participant_frontend_url }}/login

Step 3 — Place your first order!

Questions? Reply to this email or speak to your pantry coordinator.

— The Basketful Team
'''


def fix_onboarding_email(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')
    try:
        onboarding = EmailType.objects.get(name='onboarding')
        onboarding.html_content = NEW_HTML_CONTENT
        onboarding.text_content = NEW_TEXT_CONTENT
        # Record the new variables in available_variables if the field exists
        current_vars = onboarding.available_variables or ''
        new_vars = '{{ participant_customer_number }}, {{ participant_frontend_url }}'
        if new_vars not in current_vars:
            onboarding.available_variables = (
                (current_vars + ', ' + new_vars).strip(', ')
                if current_vars else new_vars
            )
        onboarding.save()
    except EmailType.DoesNotExist:
        pass  # Fresh environment — nothing to migrate


def reverse_fix(apps, schema_editor):
    pass  # One-way fix; reverting would re-introduce the credential bug


class Migration(migrations.Migration):

    dependencies = [
        ('log', '0009_emaillog_delivery_status'),
    ]

    operations = [
        migrations.RunPython(fix_onboarding_email, reverse_fix),
    ]

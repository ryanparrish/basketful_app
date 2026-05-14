"""Add order_window_opened EmailType."""
from django.db import migrations


ORDER_WINDOW_OPENED_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Order Window is Open</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f9fafb; margin: 0; padding: 20px; }
        .container { max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .header { background: linear-gradient(135deg, #16a34a 0%, #15803d 100%); padding: 36px 32px; text-align: center; }
        .logo { font-size: 28px; margin-bottom: 8px; }
        .header h2 { color: #ffffff; margin: 0; font-size: 22px; font-weight: 700; }
        .header p.subtitle { color: #dcfce7; margin: 6px 0 0; font-size: 14px; }
        .content { padding: 32px; color: #374151; font-size: 15px; line-height: 1.6; }
        .btn-container { text-align: center; padding: 0 32px 32px; }
        .btn { display: inline-block; background: #16a34a; color: #ffffff; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-size: 16px; font-weight: 600; }
        .info-box { background: #f0fdf4; border-left: 4px solid #16a34a; border-radius: 4px; padding: 16px; margin: 0 32px 32px; font-size: 14px; color: #374151; }
        .footer { padding: 24px 32px; text-align: center; color: #9ca3af; font-size: 13px; border-top: 1px solid #f3f4f6; }
        .signature { margin-top: 16px; color: #6b7280; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🛒 Basketful</div>
            <h2>Your Order Window is Open!</h2>
            <p class="subtitle">Love Your Neighbor Life Skills Program</p>
        </div>
        <div class="content">
            <p>Hi {{ participant_name }},</p>
            <p>Great news — the order window for <strong>{{ program_name }}</strong> is now open. You can place your grocery order right now.</p>
            <p>Your window closes on <strong>{{ closes_at }}</strong>, so don\'t wait too long!</p>
        </div>
        <div class="btn-container">
            <a href="{{ participant_frontend_url }}" class="btn">Place My Order</a>
        </div>
        <div class="info-box">
            <p><strong>Your Customer Number:</strong> {{ participant_customer_number }}</p>
            <p style="margin-bottom: 0;">Use this number to log in at the link above.</p>
        </div>
        <div class="footer">
            <p>If the button above doesn\'t work, copy and paste this link into your browser:</p>
            <p style="word-break: break-all; color: #16a34a;">{{ participant_frontend_url }}</p>
            <p class="signature">Thanks,<br><strong>The Basketful Team</strong></p>
        </div>
    </div>
</body>
</html>'''

ORDER_WINDOW_OPENED_TEXT = '''Hi {{ participant_name }},

Great news — the order window for {{ program_name }} is now open. You can place your grocery order right now.

Your window closes on {{ closes_at }}, so don\'t wait too long!

Place your order here:
{{ participant_frontend_url }}

Your Customer Number: {{ participant_customer_number }}

Thanks,
The Basketful Team'''


def seed_order_window_opened_email_type(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')
    EmailType.objects.update_or_create(
        name='order_window_opened',
        defaults=dict(
            display_name='Order Window Opened',
            subject='Your order window is open — {{ program_name }}',
            html_content=ORDER_WINDOW_OPENED_HTML,
            text_content=ORDER_WINDOW_OPENED_TEXT,
            html_template='',
            text_template='',
            reply_to='',
            available_variables=(
                '{{ participant_name }}, {{ participant_customer_number }}, '
                '{{ program_name }}, {{ closes_at }}, {{ participant_frontend_url }}'
            ),
            description=(
                'Sent to participants when their program\'s order window opens. '
                'One email per window cycle per participant (deduplicated by opens_at).'
            ),
            is_active=True,
        ),
    )


def reverse_seed(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')
    EmailType.objects.filter(name='order_window_opened').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('log', '0010_fix_onboarding_email_customer_number'),
    ]

    operations = [
        migrations.RunPython(seed_order_window_opened_email_type, reverse_seed),
    ]

"""Add stock_forecast_alert EmailType (Issue #148; staff-facing, English only)."""
from django.db import migrations


STOCK_FORECAST_ALERT_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Forecast Alert</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f9fafb; margin: 0; padding: 20px; }
        .container { max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .header { background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%); padding: 36px 32px; text-align: center; }
        .logo { font-size: 28px; margin-bottom: 8px; }
        .header h2 { color: #ffffff; margin: 0; font-size: 22px; font-weight: 700; }
        .header p.subtitle { color: #dbeafe; margin: 6px 0 0; font-size: 14px; }
        .content { padding: 32px; color: #374151; font-size: 15px; line-height: 1.6; }
        table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }
        th { text-align: left; background: #eff6ff; padding: 8px; color: #1e3a8a; }
        td { padding: 8px; border-bottom: 1px solid #f3f4f6; }
        td.num, th.num { text-align: right; }
        .footer { padding: 24px 32px; text-align: center; color: #9ca3af; font-size: 13px; border-top: 1px solid #f3f4f6; }
        .signature { margin-top: 16px; color: #6b7280; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🛒 Basketful</div>
            <h2>Stock Forecast Alert</h2>
            <p class="subtitle">Inventory Management</p>
        </div>
        <div class="content">
            <p>At the current rate of orders, {{ product_count }} product(s) will run out within <strong>{{ alert_weeks }} week(s)</strong>:</p>
            <table>
                <tr><th>Product</th><th class="num">Available</th><th class="num">Per week</th><th>Runs out about</th><th class="num">Suggested reorder</th></tr>
                {% for product in products %}<tr><td><strong>{{ product.name }}</strong></td><td class="num">{{ product.available }}</td><td class="num">{{ product.weekly_usage }}</td><td>{{ product.runout_date }}</td><td class="num">{{ product.suggested_reorder }}</td></tr>
                {% endfor %}
            </table>
            <p>Available is stock on hand minus pending orders. The full forecast and a reorder list are on the Stock Forecast page in the staff app.</p>
            <p>Each product alerts once; you won't be emailed about it again until its forecast recovers and then drops again.</p>
        </div>
        <div class="footer">
            <p class="signature">Thanks,<br><strong>The Basketful Team</strong></p>
        </div>
    </div>
</body>
</html>'''

STOCK_FORECAST_ALERT_TEXT = '''Stock Forecast Alert

At the current rate of orders, {{ product_count }} product(s) will run out within {{ alert_weeks }} week(s):

{% for product in products %}- {{ product.name }}: {{ product.available }} available, about {{ product.weekly_usage }}/week, runs out about {{ product.runout_date }}. Suggested reorder: {{ product.suggested_reorder }}
{% endfor %}
Available is stock on hand minus pending orders. The full forecast and a reorder list are on the Stock Forecast page in the staff app.

Each product alerts once; you won't be emailed about it again until its forecast recovers and then drops again.

Thanks,
The Basketful Team'''

STOCK_FORECAST_ALERT_SUBJECT = (
    'Stock forecast: {{ product_count }} product(s) running out within {{ alert_weeks }} week(s)'
)


def seed(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')
    EmailType.objects.update_or_create(
        name='stock_forecast_alert',
        defaults=dict(
            display_name='Stock Forecast Alert',
            subject=STOCK_FORECAST_ALERT_SUBJECT,
            subject_en=STOCK_FORECAST_ALERT_SUBJECT,
            html_content=STOCK_FORECAST_ALERT_HTML,
            html_content_en=STOCK_FORECAST_ALERT_HTML,
            text_content=STOCK_FORECAST_ALERT_TEXT,
            text_content_en=STOCK_FORECAST_ALERT_TEXT,
            html_template='',
            text_template='',
            reply_to='',
            available_variables=(
                '{{ products }} (list; loop with {% for product in products %}: '
                'product.name, product.available, product.weekly_usage, '
                'product.weeks_left, product.runout_date, product.suggested_reorder), '
                '{{ product_count }}, {{ alert_weeks }}'
            ),
            description=(
                'Daily digest to the low-inventory alert recipients listing '
                'products newly forecast to run out within the forecast alert '
                'window (Settings > Inventory Alerts). One alert per episode: a '
                "product's forecast must recover before it can alert again. "
                'Staff-facing; English only.'
            ),
            is_active=True,
        ),
    )


def unseed(apps, schema_editor):
    apps.get_model('log', 'EmailType').objects.filter(name='stock_forecast_alert').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('log', '0018_email_studio_fields'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

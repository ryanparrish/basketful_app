"""Add low_inventory_alert EmailType (staff-facing, English only)."""
from django.db import migrations


LOW_INVENTORY_ALERT_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Low Inventory Alert</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f9fafb; margin: 0; padding: 20px; }
        .container { max-width: 580px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
        .header { background: linear-gradient(135deg, #d97706 0%, #b45309 100%); padding: 36px 32px; text-align: center; }
        .logo { font-size: 28px; margin-bottom: 8px; }
        .header h2 { color: #ffffff; margin: 0; font-size: 22px; font-weight: 700; }
        .header p.subtitle { color: #fef3c7; margin: 6px 0 0; font-size: 14px; }
        .content { padding: 32px; color: #374151; font-size: 15px; line-height: 1.6; }
        .product-list { background: #fffbeb; border-left: 4px solid #d97706; border-radius: 4px; padding: 16px 16px 16px 32px; margin: 16px 0; font-size: 14px; color: #374151; }
        .product-list li { margin-bottom: 6px; }
        .footer { padding: 24px 32px; text-align: center; color: #9ca3af; font-size: 13px; border-top: 1px solid #f3f4f6; }
        .signature { margin-top: 16px; color: #6b7280; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🛒 Basketful</div>
            <h2>Low Inventory Alert</h2>
            <p class="subtitle">Inventory Management</p>
        </div>
        <div class="content">
            <p>The following {{ product_count }} product(s) have dropped to or below the low-stock threshold of <strong>{{ threshold }}</strong>:</p>
            <ul class="product-list">
            {% for product in products %}<li><strong>{{ product.name }}</strong> — {{ product.quantity_in_stock }} in stock</li>
            {% endfor %}</ul>
            <p>Each product alerts once per low episode — you won't be emailed about these products again until their stock recovers above the threshold and then drops again.</p>
        </div>
        <div class="footer">
            <p class="signature">Thanks,<br><strong>The Basketful Team</strong></p>
        </div>
    </div>
</body>
</html>'''

LOW_INVENTORY_ALERT_TEXT = '''Low Inventory Alert

The following {{ product_count }} product(s) have dropped to or below the low-stock threshold of {{ threshold }}:

{% for product in products %}- {{ product.name }} — {{ product.quantity_in_stock }} in stock
{% endfor %}
Each product alerts once per low episode — you won't be emailed about these products again until their stock recovers above the threshold and then drops again.

Thanks,
The Basketful Team'''

LOW_INVENTORY_ALERT_SUBJECT = (
    'Low inventory alert — {{ product_count }} product(s) at or below {{ threshold }}'
)


def seed_low_inventory_alert_email_type(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')
    EmailType.objects.update_or_create(
        name='low_inventory_alert',
        defaults=dict(
            display_name='Low Inventory Alert',
            subject=LOW_INVENTORY_ALERT_SUBJECT,
            subject_en=LOW_INVENTORY_ALERT_SUBJECT,
            html_content=LOW_INVENTORY_ALERT_HTML,
            html_content_en=LOW_INVENTORY_ALERT_HTML,
            text_content=LOW_INVENTORY_ALERT_TEXT,
            text_content_en=LOW_INVENTORY_ALERT_TEXT,
            html_template='',
            text_template='',
            reply_to='',
            available_variables=(
                '{{ products }} (list — loop with {% for product in products %}: '
                'product.name, product.quantity_in_stock), '
                '{{ threshold }}, {{ product_count }}'
            ),
            description=(
                'Sent to members of the Inventory Managers group when active '
                'products drop to or below the configured low-stock threshold. '
                'One alert per low episode: a product must rise back above the '
                'threshold to re-arm. Staff-facing — English only.'
            ),
            is_active=True,
        ),
    )


def reverse_seed(apps, schema_editor):
    EmailType = apps.get_model('log', 'EmailType')
    EmailType.objects.filter(name='low_inventory_alert').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('log', '0015_copy_email_content_to_english_columns'),
    ]

    operations = [
        migrations.RunPython(seed_low_inventory_alert_email_type, reverse_seed),
    ]

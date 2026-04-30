from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('log', '0008_graceallowancelog'),
    ]

    operations = [
        migrations.AddField(
            model_name='emaillog',
            name='delivery_status',
            field=models.CharField(
                choices=[
                    ('unknown', 'Unknown'),
                    ('delivered', 'Delivered'),
                    ('bounced', 'Bounced'),
                    ('complained', 'Complained'),
                    ('unsubscribed', 'Unsubscribed'),
                    ('failed', 'Failed'),
                ],
                default='unknown',
                help_text='Mailgun delivery status fetched via Events API',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='emaillog',
            name='delivery_checked_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='When we last polled Mailgun for delivery status',
            ),
        ),
    ]

"""Add retry_count to EmailLog for soft dead-letter queue tracking."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('log', '0012_merge_0011_fix_email_template_escaped_quotes_0011_seed_order_window_opened_email_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='emaillog',
            name='retry_count',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='Number of times a failed send has been re-dispatched by the DLQ beat task',
            ),
        ),
    ]

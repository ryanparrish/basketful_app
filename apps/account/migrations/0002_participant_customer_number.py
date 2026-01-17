# Generated migration - adds customer_number field to Participant

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='participant',
            name='customer_number',
            field=models.CharField(blank=True, help_text='Customer number format: C-XXX-D (e.g., C-BKM-7)', max_length=10, null=True, unique=True),
        ),
    ]

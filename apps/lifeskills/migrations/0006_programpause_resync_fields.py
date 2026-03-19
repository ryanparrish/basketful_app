from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('lifeskills', '0005_programpause_archived_programpause_archived_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='programpause',
            name='last_resync_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='programpause',
            name='last_resync_by_username',
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
    ]

from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('pantry', '0076_alter_category_table'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                ('name', models.CharField(max_length=100)),
            ],
            options={
                'db_table': 'pantry_category',
            },
        ),
    ]
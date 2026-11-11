import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_specialist_booking_version_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Tip',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Сумма')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Создан')),
                ('booking', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='tips', to='core.booking', verbose_name='Запись')),
            ],
            options={
                'verbose_name': 'Чаевые',
                'verbose_name_plural': 'Чаевые',
                'ordering': ['-created_at'],
            },
        ),
    ]

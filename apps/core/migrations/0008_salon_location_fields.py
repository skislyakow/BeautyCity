from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_remove_sitesettings'),
    ]

    operations = [
        migrations.AddField(
            model_name='salon',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Широта'),
        ),
        migrations.AddField(
            model_name='salon',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True, verbose_name='Долгота'),
        ),
        migrations.AddField(
            model_name='salon',
            name='working_hours',
            field=models.CharField(blank=True, default='с 10:00 до 20:00  без выходных', max_length=100, verbose_name='Часы работы'),
        ),
    ]

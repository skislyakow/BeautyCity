from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0006_add_tip_model"),
    ]

    operations = [
        migrations.DeleteModel(
            name="SiteSettings",
        ),
    ]

from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import migrations


STATIC_IMG_DIR = Path(settings.BASE_DIR) / "static" / "img"

# Соответствие услуг картинкам по дизайну
# (вёрстка+фронтенд v2/index.html, servicesSlider):
# service1 = Дневной макияж, service2 = Маникюр, service3 = Укладка волос,
# service4 = Укладка волос (3 000), service5 = Педикюр, service6 = Окрашивание волос.
NEW_IMAGE_BY_TITLE = {
    "Окрашивание волос": "services/service6.svg",
    "Укладка волос": "services/service3.svg",
    "Маникюр. Классический": "services/service2.svg",
    "Педикюр": "services/service5.svg",
    "Наращивание ногтей": "services/service2.svg",
    "Дневной макияж": "services/service1.svg",
    "Свадебный макияж": "services/service1.svg",
    "Вечерний макияж": "services/service1.svg",
}


def fix_procedure_images(apps, schema_editor):
    Procedure = apps.get_model("core", "Procedure")
    procedures = list(Procedure.objects.all())

    for proc in procedures:
        name = proc.image.name
        if name and name.startswith("procedures/service"):
            proc.image.storage.delete(name)

    for proc in procedures:
        rel = NEW_IMAGE_BY_TITLE.get(proc.title)
        if not rel:
            continue
        src = STATIC_IMG_DIR / rel
        if not src.exists():
            continue
        with src.open("rb") as fh:
            proc.image.save(src.name, File(fh), save=True)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_review"),
    ]

    operations = [
        migrations.RunPython(fix_procedure_images, migrations.RunPython.noop),
    ]

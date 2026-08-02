from django.core.management.base import BaseCommand
from apps.core.models import Salon, Procedure, Specialist


# специальность (ключевые слова в bio) -> ключевые слова в названии услуги (Procedure.title)
SPECIALTY_KEYWORDS = {
    "маникюр": ["маникюр", "педикюр", "ногт"],
    "педикюр": ["маникюр", "педикюр", "ногт"],
    "парикмахер": ["волос", "укладка", "окраш", "стриж"],
    "стилист": ["волос", "укладка", "окраш", "стриж"],
    "визажист": ["макияж"],
    "макияж": ["макияж"],
}


class Command(BaseCommand):
    help = "Привязывает мастеров к услугам по совпадению ключевых слов в bio, вне зависимости от имён"

    def handle(self, *args, **options):
        salons = list(Salon.objects.all())
        procedures = list(Procedure.objects.all())
        specialists = Specialist.objects.all()

        if not salons or not procedures:
            self.stdout.write(self.style.WARNING("Сначала нужны салоны и услуги (seed_demo_data)"))
            return

        for specialist in specialists:
            bio_lower = (specialist.bio or "").lower()

            matched_keywords = set()
            for specialty_kw, procedure_kws in SPECIALTY_KEYWORDS.items():
                if specialty_kw in bio_lower:
                    matched_keywords.update(procedure_kws)

            if not matched_keywords:
                self.stdout.write(self.style.WARNING(
                    f'{specialist.full_name} (bio="{specialist.bio}"): специальность не распознана, пропускаю — заполни вручную в /admin/'
                ))
                continue

            matched_procedures = [
                p for p in procedures
                if any(kw in p.title.lower() for kw in matched_keywords)
            ]

            if not matched_procedures:
                self.stdout.write(self.style.WARNING(
                    f'{specialist.full_name}: под специальность "{specialist.bio}" не нашлось подходящих услуг'
                ))
                continue

            specialist.procedures.set(matched_procedures)
            for salon in salons:
                specialist.salons.get_or_create(salon=salon)

            self.stdout.write(self.style.SUCCESS(
                f"{specialist.full_name} ({specialist.bio}) -> {', '.join(p.title for p in matched_procedures)}"
            ))

        self.stdout.write(self.style.SUCCESS("Готово!"))

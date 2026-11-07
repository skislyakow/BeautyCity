from django.core.management.base import BaseCommand

from apps.core.management.commands.seed_db import seed_shifts
from apps.core.models import Specialist


class Command(BaseCommand):
    help = "Генерирует рабочие смены (с 10:00 до 20:00) на 30 дней вперед для всех существующих специалистов"

    def handle(self, *args, **options):
        specialists = list(Specialist.objects.all())

        if not specialists:
            self.stdout.write(
                self.style.WARNING("Нет ни одного специалиста. Сначала добавьте мастеров.")
            )
            return

        self.stdout.write("Начинаю генерацию расписания...")
        created_count = seed_shifts(specialists)
        self.stdout.write(
            self.style.SUCCESS(f"Готово! Успешно создано новых смен: {created_count}")
        )

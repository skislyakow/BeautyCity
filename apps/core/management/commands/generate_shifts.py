from datetime import timedelta, time
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.core.models import Specialist, SpecialistSalon, WorkShift


class Command(BaseCommand):
    help = "Генерирует рабочие смены (с 10:00 до 20:00) на 30 дней вперед для всех существующих специалистов"

    def handle(self, *args, **options):
        specialists = list(Specialist.objects.all())

        if not specialists:
            self.stdout.write(self.style.WARNING("Нет ни одного специалиста. Сначала добавьте мастеров."))
            return

        today = timezone.localdate()
        work_days = [today + timedelta(days=i) for i in range(30)]
        start = time(10, 0)
        end = time(20, 0)

        created_count = 0
        self.stdout.write("Начинаю генерацию расписания...")

        for day in work_days:
            for i, specialist in enumerate(specialists):
                if day.weekday() == (i % 7):
                    continue
                salon_link = SpecialistSalon.objects.filter(specialist=specialist).first()
                if not salon_link:
                    continue

                shift, created = WorkShift.objects.get_or_create(
                    salon=salon_link.salon,
                    specialist=specialist,
                    date=day,
                    defaults={
                        "start_time": start,
                        "end_time": end,
                    }
                )

                if created:
                    created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Готово! Успешно создано новых смен: {created_count}"))
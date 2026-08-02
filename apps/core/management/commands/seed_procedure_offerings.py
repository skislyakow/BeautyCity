from django.core.management.base import BaseCommand
from apps.core.models import Salon, Procedure, ProcedureOffering


class Command(BaseCommand):
    help = "Создаёт ProcedureOffering для всех комбинаций салон×услуга, которых ещё нет (цена = base_price услуги)"

    def handle(self, *args, **options):
        salons = Salon.objects.all()
        procedures = Procedure.objects.all()

        if not salons.exists():
            self.stdout.write(self.style.WARNING("Нет ни одного салона — сначала запусти seed_demo_data"))
            return
        if not procedures.exists():
            self.stdout.write(self.style.WARNING("Нет ни одной услуги — сначала запусти seed_demo_data"))
            return

        created_count = 0
        for salon in salons:
            for procedure in procedures:
                offering, created = ProcedureOffering.objects.get_or_create(
                    salon=salon,
                    procedure=procedure,
                    defaults={"price": procedure.base_price},
                )
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"Создано: {offering}"))

        self.stdout.write(self.style.SUCCESS(f"Готово! Создано новых связок: {created_count}"))
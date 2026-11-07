from django.core.management.base import BaseCommand

from apps.core.management.commands.seed_db import seed_offerings
from apps.core.models import Procedure, Salon


class Command(BaseCommand):
    help = "Создаёт ProcedureOffering для всех комбинаций салон×услуга, которых ещё нет (цена = base_price услуги)"

    def handle(self, *args, **options):
        salons = list(Salon.objects.all())
        procedures = {p.title: p for p in Procedure.objects.all()}

        if not salons:
            self.stdout.write(self.style.WARNING("Нет ни одного салона — сначала запусти seed_db"))
            return
        if not procedures:
            self.stdout.write(self.style.WARNING("Нет ни одной услуги — сначала запусти seed_db"))
            return

        seed_offerings(salons, procedures)
        self.stdout.write(self.style.SUCCESS("Готово! Связки салон×услуга актуализированы."))

from datetime import date, timedelta, time
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import (
    Salon, Procedure, ProcedureOffering, Specialist, SpecialistSalon,
    WorkShift, PromoCode, Booking, SiteSettings, CustomerProfile,
    ConsentDocument, ConsentAcceptance,
)


SALONS = [
    {"name": "BeautyCity Пушкинская", "address": "ул. Пушкинская, д. 78А", "phone": "+79179023800"},
    {"name": "BeautyCity Ленина", "address": "ул. Ленина, д. 211", "phone": "+79179023800"},
    {"name": "BeautyCity Красная", "address": "ул. Красная, д. 10", "phone": "+79179023800"},
]

PROCEDURES = [
    {"title": "Окрашивание волос", "duration_minutes": 120, "base_price": "5000.00"},
    {"title": "Укладка волос", "duration_minutes": 60, "base_price": "1500.00"},
    {"title": "Маникюр. Классический", "duration_minutes": 60, "base_price": "1400.00"},
    {"title": "Педикюр", "duration_minutes": 60, "base_price": "1400.00"},
    {"title": "Наращивание ногтей", "duration_minutes": 90, "base_price": "3000.00"},
    {"title": "Дневной макияж", "duration_minutes": 45, "base_price": "1400.00"},
    {"title": "Свадебный макияж", "duration_minutes": 90, "base_price": "3000.00"},
    {"title": "Вечерний макияж", "duration_minutes": 60, "base_price": "2000.00"},
]

SPECIALISTS = [
    # Пушкинская
    {"full_name": "Елизавета Лапина", "bio": "Мастер маникюра", "experience": "3 г. 10 мес.", "salon_idx": 0, "procedure_titles": ["Маникюр. Классический", "Педикюр", "Наращивание ногтей"]},
    {"full_name": "Анна Сергеева", "bio": "Парикмахер", "experience": "4 г. 9 мес.", "salon_idx": 0, "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Ева Колесова", "bio": "Визажист", "experience": "1 г. 2 мес.", "salon_idx": 0, "procedure_titles": ["Дневной макияж", "Свадебный макияж", "Вечерний макияж"]},
    {"full_name": "Мария Суворова", "bio": "Стилист", "experience": "1 г. 1 мес.", "salon_idx": 0, "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Мария Максимова", "bio": "Визажист", "experience": "3 г. 1 мес.", "salon_idx": 0, "procedure_titles": ["Дневной макияж", "Свадебный макияж", "Вечерний макияж"]},
    {"full_name": "Анастасия Сергеева", "bio": "Визажист", "experience": "2 г. 5 мес.", "salon_idx": 0, "procedure_titles": ["Дневной макияж", "Вечерний макияж"]},
    # Ленина
    {"full_name": "Дарья Мартынова", "bio": "Мастер маникюра", "experience": "2 г. 0 мес.", "salon_idx": 1, "procedure_titles": ["Маникюр. Классический", "Педикюр", "Наращивание ногтей"]},
    {"full_name": "Амина Абрамова", "bio": "Парикмахер", "experience": "3 г. 3 мес.", "salon_idx": 1, "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Милана Романова", "bio": "Визажист", "experience": "1 г. 8 мес.", "salon_idx": 1, "procedure_titles": ["Дневной макияж", "Свадебный макияж", "Вечерний макияж"]},
    {"full_name": "Диана Чернова", "bio": "Стилист", "experience": "4 г. 0 мес.", "salon_idx": 1, "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Полина Лукьянова", "bio": "Визажист", "experience": "2 г. 2 мес.", "salon_idx": 1, "procedure_titles": ["Дневной макияж", "Свадебный макияж"]},
    {"full_name": "Вера Дмитриева", "bio": "Визажист", "experience": "1 г. 6 мес.", "salon_idx": 1, "procedure_titles": ["Дневной макияж", "Вечерний макияж"]},
    # Красная
    {"full_name": "Зоя Матвеева", "bio": "Универсал", "experience": "5 г. 0 мес.", "salon_idx": 2, "procedure_titles": ["Маникюр. Классический", "Педикюр", "Укладка волос"]},
    {"full_name": "Мария Родина", "bio": "Мастер маникюра", "experience": "3 г. 6 мес.", "salon_idx": 2, "procedure_titles": ["Маникюр. Классический", "Педикюр", "Наращивание ногтей"]},
    {"full_name": "Дарья Попова", "bio": "Парикмахер", "experience": "2 г. 9 мес.", "salon_idx": 2, "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Ева Семенова", "bio": "Визажист", "experience": "1 г. 4 мес.", "salon_idx": 2, "procedure_titles": ["Дневной макияж", "Свадебный макияж", "Вечерний макияж"]},
    {"full_name": "Вера Романова", "bio": "Стилист", "experience": "3 г. 0 мес.", "salon_idx": 2, "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Валерия Зуева", "bio": "Визажист", "experience": "2 г. 1 мес.", "salon_idx": 2, "procedure_titles": ["Дневной макияж", "Свадебный макияж"]},
]

PROMO_CODES = [
    {"code": "kid20", "description": "Скидка 20% на первую услугу", "discount_percent": 20},
    {"code": "birthday", "description": "Скидка 15% в день рождения", "discount_percent": 15},
    {"code": "man10", "description": "Скидка 10% для мужчин", "discount_percent": 10},
]


def seed_salons():
    objs = []
    for data in SALONS:
        obj, _ = Salon.objects.get_or_create(name=data["name"], defaults=data)
        objs.append(obj)
    return objs


def seed_procedures():
    objs = {}
    for data in PROCEDURES:
        obj, _ = Procedure.objects.get_or_create(title=data["title"], defaults=data)
        objs[obj.title] = obj
    return objs


def seed_offerings(salons, procedures):
    for salon in salons:
        for procedure in procedures.values():
            price = procedure.base_price
            ProcedureOffering.objects.get_or_create(
                salon=salon, procedure=procedure,
                defaults={"price": price},
            )


def seed_specialists(salons, procedures):
    for sp_data in SPECIALISTS:
        specialist, _ = Specialist.objects.get_or_create(
            full_name=sp_data["full_name"],
            defaults={
                "bio": sp_data["bio"],
                "experience": sp_data["experience"],
            },
        )
        for title in sp_data["procedure_titles"]:
            if title in procedures:
                specialist.procedures.add(procedures[title])
        salon = salons[sp_data["salon_idx"]]
        SpecialistSalon.objects.get_or_create(
            specialist=specialist, salon=salon,
        )

    return Specialist.objects.all()


def seed_shifts(specialists, salons):
    today = timezone.localdate()
    work_days = [today + timedelta(days=i) for i in range(14)]
    start = time(10, 0)
    end = time(20, 0)
    created = 0
    for day in work_days:
        for specialist in specialists:
            salon = SpecialistSalon.objects.filter(specialist=specialist).first()
            if not salon:
                continue
            _, was = WorkShift.objects.get_or_create(
                salon=salon.salon,
                specialist=specialist,
                date=day,
                start_time=start,
                end_time=end,
            )
            if was:
                created += 1


def seed_promocodes():
    for data in PROMO_CODES:
        PromoCode.objects.get_or_create(
            code=data["code"],
            defaults={
                "description": data["description"],
                "discount_percent": data["discount_percent"],
                "is_active": True,
            },
        )


def seed_sitesettings():
    SiteSettings.objects.get_or_create(
        pk=1, defaults={"manager_phone": "+79179023800"},
    )


class Command(BaseCommand):
    help = "Заполняет БД тестовыми данными (салоны, услуги, мастера, расписание, промокоды)"

    def handle(self, *args, **options):
        with transaction.atomic():
            self.stdout.write("Создание салонов...")
            salons = seed_salons()
            self.stdout.write(f"  {len(salons)} салонов")

            self.stdout.write("Создание услуг...")
            procedures = seed_procedures()
            self.stdout.write(f"  {len(procedures)} услуг")

            self.stdout.write("Создание цен по салонам...")
            seed_offerings(salons, procedures)
            self.stdout.write("  OK")

            self.stdout.write("Создание мастеров...")
            specialists = seed_specialists(salons, procedures)
            self.stdout.write(f"  {len(specialists)} мастеров")

            self.stdout.write("Создание расписания на 14 дней...")
            seed_shifts(specialists, salons)

            self.stdout.write("Создание промокодов...")
            seed_promocodes()

            self.stdout.write("Создание настроек сайта...")
            seed_sitesettings()

        self.stdout.write(self.style.SUCCESS("БД успешно заполнена"))

import os
from datetime import date, datetime, timedelta, time

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.timezone import make_aware

from apps.core.models import (
    Salon, Procedure, ProcedureOffering, Specialist, SpecialistSalon,
    WorkShift, PromoCode, Booking, SiteSettings, CustomerProfile,
    ConsentDocument, ConsentAcceptance, Review,
)


STATIC_IMG_DIR = settings.BASE_DIR / "static" / "img"

SALONS = [
    {"name": "BeautyCity Пушкинская", "address": "ул. Пушкинская, д. 78А", "phone": "+79179023800", "image": "salons/salon1.svg"},
    {"name": "BeautyCity Ленина", "address": "ул. Ленина, д. 211", "phone": "+79179023800", "image": "salons/salon2.svg"},
    {"name": "BeautyCity Красная", "address": "ул. Красная, д. 10", "phone": "+79179023800", "image": "salons/salon3.svg"},
]

PROCEDURES = [
    {"title": "Окрашивание волос", "duration_minutes": 120, "base_price": "5000.00", "description": "Стойкое окрашивание волос с восстановлением", "image": "services/service1.svg"},
    {"title": "Укладка волос", "duration_minutes": 60, "base_price": "1500.00", "description": "Укладка феном на укладочные средства", "image": "services/service2.svg"},
    {"title": "Маникюр. Классический", "duration_minutes": 60, "base_price": "1400.00", "description": "Классический маникюр с покрытием", "image": "services/service3.svg"},
    {"title": "Педикюр", "duration_minutes": 60, "base_price": "1400.00", "description": "Комплексный уход за стопами и ногтями", "image": "services/service4.svg"},
    {"title": "Наращивание ногтей", "duration_minutes": 90, "base_price": "3000.00", "description": "Моделирование и наращивание ногтей", "image": "services/service5.svg"},
    {"title": "Дневной макияж", "duration_minutes": 45, "base_price": "1400.00", "description": "Естественный макияж для дня", "image": "services/service6.svg"},
    {"title": "Свадебный макияж", "duration_minutes": 90, "base_price": "3000.00", "description": "Стойкий макияж для особого дня", "image": "services/service6.svg"},
    {"title": "Вечерний макияж", "duration_minutes": 60, "base_price": "2000.00", "description": "Яркий макияж для вечернего выхода", "image": "services/service6.svg"},
]

SPECIALISTS = [
    # Пушкинская (avatar 1-6)
    {"full_name": "Елизавета Лапина", "bio": "Мастер маникюра", "experience": "3 г. 10 мес.", "salon_idx": 0, "avatar": "masters/avatar/pushkinskaya/1.svg", "procedure_titles": ["Маникюр. Классический", "Педикюр", "Наращивание ногтей"]},
    {"full_name": "Анна Сергеева", "bio": "Парикмахер", "experience": "4 г. 9 мес.", "salon_idx": 0, "avatar": "masters/avatar/pushkinskaya/2.svg", "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Ева Колесова", "bio": "Визажист", "experience": "1 г. 2 мес.", "salon_idx": 0, "avatar": "masters/avatar/pushkinskaya/3.svg", "procedure_titles": ["Дневной макияж", "Свадебный макияж", "Вечерний макияж"]},
    {"full_name": "Мария Суворова", "bio": "Стилист", "experience": "1 г. 1 мес.", "salon_idx": 0, "avatar": "masters/avatar/pushkinskaya/4.svg", "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Мария Максимова", "bio": "Визажист", "experience": "3 г. 1 мес.", "salon_idx": 0, "avatar": "masters/avatar/pushkinskaya/5.svg", "procedure_titles": ["Дневной макияж", "Свадебный макияж", "Вечерний макияж"]},
    {"full_name": "Анастасия Сергеева", "bio": "Визажист", "experience": "2 г. 5 мес.", "salon_idx": 0, "avatar": "masters/avatar/pushkinskaya/6.svg", "procedure_titles": ["Дневной макияж", "Вечерний макияж"]},
    # Ленина (avatar 1-6)
    {"full_name": "Дарья Мартынова", "bio": "Мастер маникюра", "experience": "2 г. 0 мес.", "salon_idx": 1, "avatar": "masters/avatar/lenina/1.svg", "procedure_titles": ["Маникюр. Классический", "Педикюр", "Наращивание ногтей"]},
    {"full_name": "Амина Абрамова", "bio": "Парикмахер", "experience": "3 г. 3 мес.", "salon_idx": 1, "avatar": "masters/avatar/lenina/2.svg", "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Милана Романова", "bio": "Визажист", "experience": "1 г. 8 мес.", "salon_idx": 1, "avatar": "masters/avatar/lenina/3.svg", "procedure_titles": ["Дневной макияж", "Свадебный макияж", "Вечерний макияж"]},
    {"full_name": "Диана Чернова", "bio": "Стилист", "experience": "4 г. 0 мес.", "salon_idx": 1, "avatar": "masters/avatar/lenina/4.svg", "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Полина Лукьянова", "bio": "Визажист", "experience": "2 г. 2 мес.", "salon_idx": 1, "avatar": "masters/avatar/lenina/5.svg", "procedure_titles": ["Дневной макияж", "Свадебный макияж"]},
    {"full_name": "Вера Дмитриева", "bio": "Визажист", "experience": "1 г. 6 мес.", "salon_idx": 1, "avatar": "masters/avatar/lenina/6.svg", "procedure_titles": ["Дневной макияж", "Вечерний макияж"]},
    # Красная (avatar 1-6)
    {"full_name": "Зоя Матвеева", "bio": "Универсал", "experience": "5 г. 0 мес.", "salon_idx": 2, "avatar": "masters/avatar/krasnaya/1.svg", "procedure_titles": ["Маникюр. Классический", "Педикюр", "Укладка волос"]},
    {"full_name": "Мария Родина", "bio": "Мастер маникюра", "experience": "3 г. 6 мес.", "salon_idx": 2, "avatar": "masters/avatar/krasnaya/2.svg", "procedure_titles": ["Маникюр. Классический", "Педикюр", "Наращивание ногтей"]},
    {"full_name": "Дарья Попова", "bio": "Парикмахер", "experience": "2 г. 9 мес.", "salon_idx": 2, "avatar": "masters/avatar/krasnaya/3.svg", "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Ева Семенова", "bio": "Визажист", "experience": "1 г. 4 мес.", "salon_idx": 2, "avatar": "masters/avatar/krasnaya/4.svg", "procedure_titles": ["Дневной макияж", "Свадебный макияж", "Вечерний макияж"]},
    {"full_name": "Вера Романова", "bio": "Стилист", "experience": "3 г. 0 мес.", "salon_idx": 2, "avatar": "masters/avatar/krasnaya/5.svg", "procedure_titles": ["Окрашивание волос", "Укладка волос"]},
    {"full_name": "Валерия Зуева", "bio": "Визажист", "experience": "2 г. 1 мес.", "salon_idx": 2, "avatar": "masters/avatar/krasnaya/6.svg", "procedure_titles": ["Дневной макияж", "Свадебный макияж"]},
]

PROMO_CODES = [
    {"code": "kid20", "description": "Скидка 20% на первую услугу", "discount_percent": 20},
    {"code": "birthday", "description": "Скидка 15% в день рождения", "discount_percent": 15},
    {"code": "man10", "description": "Скидка 10% для мужчин", "discount_percent": 10},
]

CONSENT_TITLE = "Согласие на обработку персональных данных"

CONSENT_TEXT_LINES = [
    "Настоящим я даю своё добровольное согласие на обработку",
    "персональных данных оператором BeautyCity с использованием",
    "и без использования средств автоматизации.",
    "",
    "Перечень персональных данных: фамилия, имя, отчество,",
    "номер телефона, адрес электронной почты, история записей",
    "и заказов услуг.",
    "",
    "Цели обработки: запись на услуги, связь с клиентом,",
    "информирование об акциях и новых услугах.",
    "",
    "Согласие действует с момента подписания и может быть",
    "отозвано мной в любой момент в письменной форме.",
]

REVIEW_AUTHORS = [
    "Анна", "Мария", "Екатерина", "Ольга", "Наталья", "Ирина",
    "Дарья", "Светлана", "Полина", "Ксения", "Виктория", "Елена",
]

REVIEW_TEXTS = [
    "Очень аккуратно и внимательно. Мастер услышал все пожелания, результат превзошёл ожидания.",
    "Приятный мастер, всё сделал быстро и качественно. Вернусь ещё!",
    "Всё понравилось: чисто, профессионально, доброжелательно. Рекомендую.",
    "Отличная работа! Учли все детали, обслуживание на высшем уровне.",
    "Мастер — профи своего дела. Результат держится долго, очень довольна.",
    "Хороший сервис и приятная атмосфера. Запишусь снова без раздумий.",
    "Пришла по рекомендации, не пожалела. Всё аккуратно и точно как договаривались.",
    "Приятное впечатление: вовремя, качественно и с заботой о клиенте.",
    "Лучший мастер, у которого я была! Делает красиво и с душой.",
    "Всё отлично, спасибо за работу! Рекомендую друзьям и знакомым.",
]


def _assign_image(obj, field_name, rel_path):
    """Копирует картинку из static/img в media и заполняет поле, если оно пустое."""
    field = getattr(obj, field_name)
    if field and field.name:
        return
    src = STATIC_IMG_DIR / rel_path
    if not src.exists():
        return
    with src.open("rb") as fh:
        getattr(obj, field_name).save(src.name, File(fh), save=True)


def _cyrillic_font_path():
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _generate_consent_pdf():
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    dest_dir = settings.MEDIA_ROOT / "consents"
    dest_dir.mkdir(parents=True, exist_ok=True)
    file_name = "consent_personal_data.pdf"

    c = canvas.Canvas(str(dest_dir / file_name), pagesize=A4)
    w, h = A4

    font_name = "Helvetica"
    font_path = _cyrillic_font_path()
    if font_path:
        font_name = "Cyrillic"
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(font_name, font_path))

    c.setFont(font_name, 14)
    c.drawCentredString(w / 2, h - 25 * mm, CONSENT_TITLE)
    c.setFont(font_name, 11)

    y = h - 45 * mm
    for line in CONSENT_TEXT_LINES:
        c.drawString(25 * mm, y, line)
        y -= 7 * mm

    c.setFont(font_name, 10)
    c.drawString(25 * mm, 45 * mm, f"Дата: {timezone.localdate():%d.%m.%Y}")
    c.save()

    return f"consents/{file_name}"


def seed_salons():
    objs = []
    for data in SALONS:
        image_rel = data.pop("image")
        obj, _ = Salon.objects.get_or_create(name=data["name"], defaults=data)
        _assign_image(obj, "image", image_rel)
        objs.append(obj)
    return objs


def seed_procedures():
    objs = {}
    for data in PROCEDURES:
        image_rel = data.pop("image")
        obj, _ = Procedure.objects.get_or_create(title=data["title"], defaults=data)
        _assign_image(obj, "image", image_rel)
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
        avatar_rel = sp_data.pop("avatar")
        specialist, _ = Specialist.objects.get_or_create(
            full_name=sp_data["full_name"],
            defaults={
                "bio": sp_data["bio"],
                "experience": sp_data["experience"],
            },
        )
        _assign_image(specialist, "photo", avatar_rel)
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
    work_days = [today + timedelta(days=i) for i in range(30)]
    start = time(10, 0)
    end = time(20, 0)
    for day in work_days:
        for i, specialist in enumerate(specialists):
            if day.weekday() == (i % 7):
                continue
            salon = SpecialistSalon.objects.filter(specialist=specialist).first()
            if not salon:
                continue
            WorkShift.objects.get_or_create(
                salon=salon.salon,
                specialist=specialist,
                date=day,
                start_time=start,
                end_time=end,
            )


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


def seed_reviews(specialists):
    created = 0
    for i, specialist in enumerate(specialists):
        count = 3 + (i % 5)  # от 3 до 7 отзывов на мастера
        for j in range(count):
            author = REVIEW_AUTHORS[(i * 3 + j) % len(REVIEW_AUTHORS)]
            if (i + j) % 7 == 0:
                rating = 3
            elif (i + j) % 4 == 0:
                rating = 4
            else:
                rating = 5
            text = REVIEW_TEXTS[(i + j) % len(REVIEW_TEXTS)]
            _, was_created = Review.objects.get_or_create(
                specialist=specialist,
                author_name=author,
                defaults={"rating": rating, "text": text},
            )
            created += 1 if was_created else 0
    return created


def seed_sitesettings():
    SiteSettings.objects.get_or_create(
        pk=1, defaults={"manager_phone": "+79179023800"},
    )


def seed_consents():
    if ConsentDocument.objects.exists():
        return
    file_path = _generate_consent_pdf()
    ConsentDocument.objects.get_or_create(
        title=CONSENT_TITLE,
        defaults={"file": file_path, "is_active": True},
    )


def seed_bookings():
    if Booking.objects.exists():
        return
    specialists = list(Specialist.objects.filter(is_active=True))
    procedures = list(Procedure.objects.all())
    if not specialists or not procedures:
        return

    today = timezone.localdate()
    samples = [
        (1, 11, 0, Booking.Status.NEW),
        (2, 12, 0, Booking.Status.CONFIRMED),
        (3, 15, 0, Booking.Status.NEW),
    ]

    for offset, hour, minute, status in samples:
        specialist = specialists[(offset - 1) % len(specialists)]
        procedure = procedures[(offset - 1) % len(procedures)]
        ssl = SpecialistSalon.objects.filter(specialist=specialist).first()
        if not ssl:
            continue
        salon = ssl.salon
        offering = ProcedureOffering.objects.filter(salon=salon, procedure=procedure).first()
        if not offering:
            continue

        start_at = make_aware(datetime.combine(today + timedelta(days=offset), time(hour, minute)))
        Booking.objects.get_or_create(
            salon=salon,
            specialist=specialist,
            procedure=procedure,
            start_at=start_at,
            defaults={
                "end_at": start_at + timedelta(minutes=procedure.duration_minutes),
                "customer_name": "Тестовый клиент",
                "phone": f"+7917000000{offset}",
                "question": "Хочу уточнить детали при звонке",
                "price_original": offering.price,
                "price_final": offering.price,
                "status": status,
                "source": Booking.Source.WEB,
            },
        )


class Command(BaseCommand):
    help = "Заполняет БД тестовыми данными (салоны, услуги, мастера, расписание, промокоды, согласие, примерные записи)"

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

            self.stdout.write("Создание расписания на 30 дней...")
            seed_shifts(specialists, salons)

            self.stdout.write("Создание промокодов...")
            seed_promocodes()

            self.stdout.write("Создание отзывов...")
            created_reviews = seed_reviews(specialists)
            self.stdout.write(f"  создано {created_reviews} новых отзывов")

            self.stdout.write("Создание настроек сайта...")
            seed_sitesettings()

            self.stdout.write("Создание согласия на обработку данных...")
            seed_consents()

            self.stdout.write("Создание примерных записей...")
            seed_bookings()

        self.stdout.write(self.style.SUCCESS("БД успешно заполнена"))

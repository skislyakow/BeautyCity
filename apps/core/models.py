import re

from django.conf import settings
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.templatetags.static import static
from django.utils import timezone

phone_validator = RegexValidator(
    regex=r"^\+?\d{10,15}$",
    message="Телефон должен быть в формате +79998887766 (10–15 цифр).",
)


def normalize_phone(phone):
    phone = str(phone or "").strip()
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if not digits:
        return ""
    if digits.startswith("8") and len(digits) == 11:
        digits = "7" + digits[1:]
    if len(digits) == 10:
        digits = "7" + digits
    if digits.startswith("7") and len(digits) == 11:
        return "+" + digits
    return "+" + digits


class Salon(models.Model):
    name = models.CharField("Название", max_length=200)
    address = models.CharField("Адрес", max_length=300)
    image = models.FileField(
        "Фото салона",
        upload_to="salons/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["svg", "png", "jpg", "jpeg", "webp"])],
    )
    phone = models.CharField("Телефон салона", max_length=20, blank=True)
    working_hours = models.CharField(
        "Часы работы",
        max_length=100,
        blank=True,
        default="с 10:00 до 20:00  без выходных",
    )
    latitude = models.DecimalField(
        "Широта",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        "Долгота",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Салон"
        verbose_name_plural = "Салоны"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Procedure(models.Model):
    title = models.CharField("Процедура", max_length=200)
    image = models.FileField(
        "Фото услуги",
        upload_to="procedures/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["svg", "png", "jpg", "jpeg", "webp"])],
    )
    description = models.TextField("Описание", blank=True)
    duration_minutes = models.PositiveIntegerField("Длительность (мин)", default=60)
    base_price = models.DecimalField("Базовая цена", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Процедура"
        verbose_name_plural = "Процедуры"
        ordering = ["title"]

    def __str__(self):
        return self.title


class ProcedureOffering(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="offerings")
    procedure = models.ForeignKey(Procedure, on_delete=models.CASCADE, related_name="offerings")
    price = models.DecimalField("Цена в салоне", max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = "Процедура в салоне"
        verbose_name_plural = "Процедуры в салонах"
        constraints = [
            models.UniqueConstraint(fields=["salon", "procedure"], name="uniq_salon_procedure")
        ]

    def __str__(self):
        return f"{self.procedure} — {self.salon}"


class Specialist(models.Model):
    full_name = models.CharField("ФИО", max_length=200)
    photo = models.FileField(
        "Фото мастера",
        upload_to="specialists/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["svg", "png", "jpg", "jpeg", "webp"])],
    )
    procedures = models.ManyToManyField(
        "Procedure",
        related_name="specialists",
        verbose_name="Какие услуги делает",
        blank=True,
    )
    bio = models.TextField("Специальность", blank=True)
    experience = models.TextField("Стаж работы", blank=True)
    is_active = models.BooleanField("Активен", default=True)
    booking_version = models.PositiveIntegerField("Версия бронирования", default=0, editable=False)

    class Meta:
        verbose_name = "Специалист"
        verbose_name_plural = "Специалисты"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class SpecialistSalon(models.Model):
    specialist = models.ForeignKey(Specialist, on_delete=models.CASCADE, related_name="salons")
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="specialists")

    class Meta:
        verbose_name = "Специалист в салоне"
        verbose_name_plural = "Специалисты в салонах"
        constraints = [
            models.UniqueConstraint(fields=["specialist", "salon"], name="uniq_specialist_salon")
        ]

    def __str__(self):
        return f"{self.specialist} @ {self.salon}"


class WorkShift(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="shifts")
    specialist = models.ForeignKey(Specialist, on_delete=models.CASCADE, related_name="shifts")
    date = models.DateField("Дата")
    start_time = models.TimeField("С")
    end_time = models.TimeField("До")

    class Meta:
        verbose_name = "Смена специалиста"
        verbose_name_plural = "Смены специалистов"
        ordering = ["-date", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "salon",
                    "specialist",
                    "date",
                    "start_time",
                    "end_time",
                ],
                name="uniq_shift_exact",
            )
        ]

    def __str__(self):
        return f"{self.date} {self.start_time}-{self.end_time}: {self.specialist} ({self.salon})"


class PromoCode(models.Model):
    code = models.CharField("Промокод", max_length=30, unique=True)
    description = models.CharField("Описание", max_length=300, blank=True)
    discount_percent = models.PositiveSmallIntegerField(
        "Скидка, %", validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    is_active = models.BooleanField("Активен", default=True)
    valid_from = models.DateField("Действует с", blank=True, null=True)
    valid_to = models.DateField("Действует по", blank=True, null=True)

    class Meta:
        verbose_name = "Промокод"
        verbose_name_plural = "Промокоды"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} (-{self.discount_percent}%)"

    def is_valid_today(self, today=None) -> bool:
        today = today or timezone.localdate()
        if not self.is_active:
            return False
        if self.valid_from and today < self.valid_from:
            return False
        return not (self.valid_to and today > self.valid_to)


class ConsentDocument(models.Model):
    title = models.CharField(
        "Название",
        max_length=200,
        default="Согласие на обработку персональных данных",
    )
    file = models.FileField("PDF файл", upload_to="consents/")
    is_active = models.BooleanField("Активный", default=True)
    uploaded_at = models.DateTimeField("Загружен", auto_now_add=True)

    def __str__(self):
        return self.title


class ConsentAcceptance(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consents",
        verbose_name="Пользователь",
    )
    phone = models.CharField("Телефон", max_length=20, validators=[phone_validator], blank=True)
    document = models.ForeignKey(
        ConsentDocument, on_delete=models.PROTECT, related_name="acceptances"
    )
    accepted_at = models.DateTimeField("Принято", auto_now_add=True)

    class Meta:
        verbose_name = "Принятие согласия"
        verbose_name_plural = "Принятия согласия"
        ordering = ["-accepted_at"]

    def __str__(self):
        return f"Consent #{self.pk} @ {self.accepted_at:%Y-%m-%d %H:%M}"


def record_consent_acceptance(*, user=None, phone="", accepted=True):
    if not accepted:
        return None
    document = ConsentDocument.objects.filter(is_active=True).order_by("-uploaded_at").first()
    if not document:
        return None
    phone = normalize_phone(phone) or str(phone or "").strip()
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    return ConsentAcceptance.objects.create(user=user, phone=phone, document=document)


class CustomerProfile(models.Model):
    class Gender(models.TextChoices):
        UNKNOWN = "unknown", "Не указан"
        MALE = "male", "Мужской"
        FEMALE = "female", "Женский"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    phone = models.CharField("Телефон", max_length=20, validators=[phone_validator], blank=True)
    first_name = models.CharField("Имя", max_length=120, blank=True)
    gender = models.CharField(
        "Пол",
        max_length=10,
        choices=Gender.choices,
        default=Gender.UNKNOWN,
    )
    avatar = models.FileField(
        "Аватар",
        upload_to="avatars/",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["svg", "png", "jpg", "jpeg", "webp"])],
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Профиль клиента"
        verbose_name_plural = "Профили клиентов"

    def __str__(self):
        return f"{self.user}"

    def get_avatar_url(self):
        if self.avatar:
            try:
                return self.avatar.url
            except Exception:
                pass
        return static("img/avatars/user.svg")


class Booking(models.Model):
    class Source(models.TextChoices):
        WEB = "web", "Сайт"
        PHONE = "phone", "Звонок"

    class Status(models.TextChoices):
        NEW = "new", "Новая"
        CONFIRMED = "confirmed", "Подтверждена"
        CANCELED = "canceled", "Отменена"

    salon = models.ForeignKey(Salon, on_delete=models.PROTECT, related_name="bookings")
    procedure = models.ForeignKey(Procedure, on_delete=models.PROTECT, related_name="bookings")
    specialist = models.ForeignKey(
        Specialist,
        on_delete=models.PROTECT,
        related_name="bookings",
        null=True,
        blank=True,
    )

    customer_name = models.CharField("Имя клиента", max_length=120, blank=True)
    phone = models.CharField("Телефон", max_length=20, validators=[phone_validator])
    question = models.CharField("Вопрос", max_length=300, null=True, blank=True)

    start_at = models.DateTimeField("Начало")
    end_at = models.DateTimeField("Конец")

    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True)
    price_original = models.DecimalField("Цена без скидки", max_digits=10, decimal_places=2)
    price_final = models.DecimalField("Цена со скидкой", max_digits=10, decimal_places=2)

    source = models.CharField("Источник", max_length=10, choices=Source.choices, default=Source.WEB)
    status = models.CharField("Статус", max_length=12, choices=Status.choices, default=Status.NEW)

    created_at = models.DateTimeField("Создана", auto_now_add=True)

    payment_id = models.CharField("ID платежа", max_length=100, blank=True)

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ["-start_at"]
        indexes = [
            models.Index(fields=["salon", "start_at"]),
            models.Index(fields=["specialist", "start_at"]),
            models.Index(fields=["phone", "start_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["specialist", "start_at"],
                condition=~models.Q(status="canceled"),
                name="uniq_active_specialist_start",
            )
        ]

    def __str__(self):
        return f"{self.start_at:%Y-%m-%d %H:%M} — {self.procedure} ({self.salon})"


class CallbackRequest(models.Model):
    name = models.CharField("Имя", max_length=100, blank=True)
    phone = models.CharField("Телефон", max_length=20, validators=[phone_validator])
    is_processed = models.BooleanField("Обработано", default=False)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Заявка на звонок"
        verbose_name_plural = "Заявки на звонок"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name or 'Без имени'} — {self.phone}"


class Review(models.Model):
    specialist = models.ForeignKey(
        Specialist,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="Мастер",
    )
    author_name = models.CharField("Имя клиента", max_length=120, blank=True)
    rating = models.PositiveSmallIntegerField(
        "Оценка",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5,
    )
    text = models.TextField("Текст отзыва", blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Отзыв"
        verbose_name_plural = "Отзывы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.specialist} — {self.rating}/5 ({self.author_name})"


class Tip(models.Model):
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="tips",
        verbose_name="Запись",
    )
    amount = models.DecimalField("Сумма", max_digits=10, decimal_places=2)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Чаевые"
        verbose_name_plural = "Чаевые"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Tip {self.amount} for booking #{self.booking_id}"

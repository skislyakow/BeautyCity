from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator, FileExtensionValidator
from django.db import models
from django.utils import timezone


phone_validator = RegexValidator(
    regex=r"^\+?\d{10,15}$",
    message="Телефон должен быть в формате +79998887766 (10–15 цифр).",
)


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
    is_active = models.BooleanField("Активен", default=True)

    class Meta:
        verbose_name = "Салон"
        verbose_name_plural = "Салоны"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Procedure(models.Model):
    title = models.CharField("Процедура", max_length=200)
    image = models.FileField("Фото услуги", upload_to="procedures/",
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
    """
    Цена процедуры может отличаться по салонам.
    """
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
    photo = models.FileField("Фото мастера", upload_to="specialists/",
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

    class Meta:
        verbose_name = "Специалист"
        verbose_name_plural = "Специалисты"
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name


class SpecialistSalon(models.Model):
    """
    В каких салонах работает специалист (многие-ко-многим).
    """
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
    """
    Расписание: когда специалист работает в конкретном салоне.
    По нему можно показывать "какие специалисты когда работают".
    """
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
                fields=["salon", "specialist", "date", "start_time", "end_time"],
                name="uniq_shift_exact"
            )
        ]

    def __str__(self):
        return f"{self.date} {self.start_time}-{self.end_time}: {self.specialist} ({self.salon})"


class PromoCode(models.Model):
    """
    Промокоды: kid20 (20%), birthday (15%), man10 (10% в декабре).
    Правила лучше держать простыми на MVP: процент + период действия + флаг активен.
    """
    code = models.CharField("Промокод", max_length=30, unique=True)
    description = models.CharField("Описание", max_length=300, blank=True)
    discount_percent = models.PositiveSmallIntegerField(
        "Скидка, %",
        validators=[MinValueValidator(1), MaxValueValidator(100)]
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
        if self.valid_to and today > self.valid_to:
            return False
        return True


class ConsentDocument(models.Model):
    title = models.CharField("Название", max_length=200, default="Согласие на обработку персональных данных")
    file = models.FileField("PDF файл", upload_to="consents/")
    is_active = models.BooleanField("Активный", default=True)
    uploaded_at = models.DateTimeField("Загружен", auto_now_add=True)


class ConsentAcceptance(models.Model):
    """
    Фиксация согласия (для регистрации или оформления записи).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consents",
        verbose_name="Пользователь",
    )
    phone = models.CharField("Телефон", max_length=20, validators=[phone_validator], blank=True)
    document = models.ForeignKey(ConsentDocument, on_delete=models.PROTECT, related_name="acceptances")
    accepted_at = models.DateTimeField("Принято", auto_now_add=True)

    class Meta:
        verbose_name = "Принятие согласия"
        verbose_name_plural = "Принятия согласия"
        ordering = ["-accepted_at"]

    def __str__(self):
        return f"Consent #{self.id} @ {self.accepted_at:%Y-%m-%d %H:%M}"


class CustomerProfile(models.Model):
    """
    Удобно для подсчёта регистраций и хранения телефона.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    phone = models.CharField("Телефон", max_length=20, validators=[phone_validator], blank=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Профиль клиента"
        verbose_name_plural = "Профили клиентов"

    def __str__(self):
        return f"{self.user}"


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
    specialist = models.ForeignKey(Specialist, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True)

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

    payment_id = models.CharField('ID платежа', max_length=100, blank=True)

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ["-start_at"]
        indexes = [
            models.Index(fields=["salon", "start_at"]),
            models.Index(fields=["specialist", "start_at"]),
            models.Index(fields=["phone", "start_at"]),
        ]

    def __str__(self):
        return f"{self.start_at:%Y-%m-%d %H:%M} — {self.procedure} ({self.salon})"

    @property
    def discount_percent(self) -> int:
        if not self.promo_code:
            return 0
        return int(self.promo_code.discount_percent)


class SiteSettings(models.Model):
    """
    Чтобы "показать номер менеджера" и хранить 1-2 глобальные настройки.
    Ожидается одна запись.
    """
    manager_phone = models.CharField("Телефон менеджера", max_length=20, blank=True)

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return "Настройки сайта"


class CallbackRequest(models.Model):
    """Заявка на обратный звонок (кнопка «Перезвоните мне»)."""

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
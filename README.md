# BeautyCity —模型参考

Всё в одном приложении `apps.core`. 11 моделей, описание полей и связей — чтобы было понятно, с чем работать во вьюхах и бизнес-логике.

---

## Salon — Салон

| Поле | Тип | Описание |
|---|---|---|
| name | CharField(200) | Название |
| address | CharField(300) | Адрес |
| phone | CharField(20) | Телефон салона |
| image | FileField(upload_to='salons/') | Фото (svg/png/jpg/webp) |
| is_active | BooleanField(default=True) | Активен |

---

## Procedure — Услуга/процедура

| Поле | Тип | Описание |
|---|---|---|
| title | CharField(200) | Название |
| description | TextField | Описание |
| duration_minutes | PositiveIntegerField(default=60) | Длительность в минутах |
| base_price | DecimalField(10, 2) | Базовая цена |
| image | FileField(upload_to='procedures/') | Фото |

---

## ProcedureOffering — Услуга в салоне (цена по салонам)

| Поле | Тип | Описание |
|---|---|---|
| salon | FK → Salon | Салон |
| procedure | FK → Procedure | Услуга |
| price | DecimalField(10, 2) | Цена в этом салоне |

**constraints:** `unique(salon, procedure)`

---

## Specialist — Мастер

| Поле | Тип | Описание |
|---|---|---|
| full_name | CharField(200) | ФИО |
| photo | FileField(upload_to='specialists/') | Фото |
| bio | TextField | Специальность / описание |
| experience | TextField | Стаж работы |
| is_active | BooleanField(default=True) | Активен |
| procedures | ManyToManyField → Procedure | Какие услуги делает |

---

## SpecialistSalon — Мастер → Салон (M2M)

| Поле | Тип | Описание |
|---|---|---|
| specialist | FK → Specialist | Мастер |
| salon | FK → Salon | Салон |

**constraints:** `unique(specialist, salon)`

---

## WorkShift — Смена / расписание мастера

| Поле | Тип | Описание |
|---|---|---|
| salon | FK → Salon | Салон |
| specialist | FK → Specialist | Мастер |
| date | DateField | Дата |
| start_time | TimeField | Начало смены |
| end_time | TimeField | Конец смены |

**constraints:** `unique(salon, specialist, date, start_time, end_time)`

---

## PromoCode — Промокод

| Поле | Тип | Описание |
|---|---|---|
| code | CharField(30, unique) | Код (kid20, birthday, man10) |
| description | CharField(300) | Описание |
| discount_percent | PositiveSmallIntegerField(1-100) | Процент скидки |
| is_active | BooleanField(default=True) | Активен |
| valid_from | DateField(nullable) | Начало действия |
| valid_to | DateField(nullable) | Конец действия |

**Метод:** `is_valid_today(today=None) -> bool` — проверяет активность и даты.

---

## Booking — Запись (главная модель)

| Поле | Тип | Описание |
|---|---|---|
| salon | FK → Salon | Салон |
| procedure | FK → Procedure | Услуга |
| specialist | FK → Specialist(nullable) | Мастер |
| customer_name | CharField(120) | Имя клиента |
| phone | CharField(20) | Телефон (+7XXXXXXXXXX) |
| question | CharField(300, nullable) | Вопрос / комментарий |
| start_at | DateTimeField | Начало |
| end_at | DateTimeField | Конец |
| promo_code | FK → PromoCode(nullable) | Промокод |
| price_original | DecimalField(10, 2) | Цена без скидки |
| price_final | DecimalField(10, 2) | Цена со скидкой |
| source | CharField(choices: web/phone) | Источник |
| status | CharField(choices: new/confirmed/canceled) | Статус |
| payment_id | CharField(100, blank) | ID платежа |
| created_at | DateTimeField(auto_now_add) | Создана |

**indexes:** `(salon, start_at)`, `(specialist, start_at)`, `(phone, start_at)`

**property:** `discount_percent` — возвращает процент скидки из промокода

---

## CustomerProfile — Профиль клиента

| Поле | Тип | Описание |
|---|---|---|
| user | OneToOneField → User | Связь с Django User |
| phone | CharField(20) | Телефон |
| created_at | DateTimeField(auto_now_add) | Дата регистрации |

---

## ConsentDocument / ConsentAcceptance — Согласия

### ConsentDocument
| Поле | Тип |
|---|---|
| title | CharField(200) |
| file | FileField(upload_to='consents/') |
| is_active | BooleanField |
| uploaded_at | DateTimeField(auto_now_add) |

### ConsentAcceptance
| Поле | Тип |
|---|---|
| user | FK → User (nullable) |
| phone | CharField(20) |
| document | FK → ConsentDocument |
| accepted_at | DateTimeField(auto_now_add) |

---

## SiteSettings — Настройки сайта (одна запись)

| Поле | Тип | Описание |
|---|---|---|
| manager_phone | CharField(20) | Телефон менеджера |

---

## Полезные файлы для разработчика

| Файл | Что даёт |
|---|---|
| `apps/core/slots.py` | `get_available_slots(salon, specialist, procedure, date)` — список свободного времени |
| `apps/core/forms.py` | `BookingForm` — форма записи с валидацией телефона |
| `apps/core/payment_views.py` | `create_payment()` / `yookassa_webhook()` — оплата через ЮKassa |

## Использование в коде

```python
from apps.core.models import Salon, Procedure, Booking, PromoCode
from apps.core.slots import get_available_slots
from apps.core.forms import BookingForm

# Проверка промокода
code = PromoCode.objects.filter(code='kid20').first()
if code and code.is_valid_today():
    # применяем скидку
    price_final = price_original * (100 - code.discount_percent) / 100

# Свободные слоты
slots = get_available_slots(
    salon=salon, specialist=specialist,
    procedure=procedure, date=date
)
```

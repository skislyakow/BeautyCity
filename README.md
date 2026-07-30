# BeautyCity API

Базовый URL: `http://localhost:8000/api/`

---

## Салоны

### Список салонов

```
GET /api/salons/
```

```json
[
  {
    "id": 1,
    "name": "BeautyCity Пушкинская",
    "address": "ул. Пушкинская, д. 78А",
    "phone": "+79179023800",
    "image": "/media/salons/salon1.svg",
    "is_active": true
  }
]
```

### Услуги салона

```
GET /api/salons/<id>/procedures/
```

### Мастера салона

```
GET /api/salons/<id>/specialists/
```

---

## Услуги

### Все услуги

```
GET /api/procedures/
```

```json
[
  {
    "id": 1,
    "title": "Маникюр. Классический. Гель",
    "description": "",
    "duration_minutes": 60,
    "base_price": "2000.00",
    "image": "/media/procedures/service2.svg"
  }
]
```

### Цены на услуги по салонам

```
GET /api/procedure-offerings/
```

Возвращает: `id`, `salon`, `procedure`, `price` (вложенные объекты салона и услуги)

---

## Мастера

### Список мастеров (с фильтрами)

```
GET /api/specialists/?salon=1&procedure=2
```

Оба фильтра опциональны. Без них — все мастера.

```json
[
  {
    "id": 1,
    "full_name": "Елизавета Лапина",
    "photo": "/media/specialists/1.svg",
    "bio": "Мастер маникюра",
    "experience": "3 г. 10 мес.",
    "is_active": true,
    "procedures": [
      {
        "id": 2,
        "title": "Маникюр. Классический. Гель",
        "description": "",
        "duration_minutes": 60,
        "base_price": "2000.00",
        "image": "/media/procedures/service2.svg"
      }
    ]
  }
]
```

### Услуги мастера

```
GET /api/specialists/<id>/procedures/
```

### Салоны мастера

```
GET /api/specialists/<id>/salons/
```

---

## Слоты (свободное время)

```
GET /api/slots/?salon=1&specialist=1&procedure=2&date=2026-08-01
```

Все параметры обязательны.

```json
{
  "slots": ["10:00", "10:30", "12:00", "12:30", "15:00", "16:30", "17:00", "18:30", "19:00"]
}
```

Учитывает: расписание мастера (WorkShift), занятые записи (Booking), длительность процедуры (Procedure.duration_minutes), шаг 30 минут, текущее время (прошедшие слоты не возвращаются).

---

## Записи (Booking)

### Создать запись

```
POST /api/bookings/
Content-Type: application/json

{
  "salon": 1,
  "procedure": 2,
  "specialist": 1,
  "customer_name": "Алиса",
  "phone": "+79998887766",
  "question": "Хочу яркий цвет",
  "start_at": "2026-08-01T15:00:00+03:00",
  "end_at": "2026-08-01T16:00:00+03:00",
  "promo_code": null
}
```

Поля: `salon`, `procedure`, `specialist`, `customer_name`, `phone`, `question`, `start_at`, `end_at`, `promo_code` (опционально).

Валидация: мастер работает в салоне, слот свободен.

Успех (201):

```json
{
  "id": 1,
  "customer_name": "Алиса",
  "phone": "+79998887766",
  "question": "Хочу яркий цвет",
  "salon": { ... },
  "procedure": { ... },
  "specialist": { ... },
  "start_at": "2026-08-01T15:00:00+03:00",
  "end_at": "2026-08-01T16:00:00+03:00",
  "status": "new",
  "source": "web",
  "price_final": "2000.00",
  "created_at": "2026-07-30T12:00:00+03:00"
}
```

### Мои записи

```
GET /api/my-bookings/?phone=+79998887766
```

Возвращает записи по номеру телефона, от новых к старым.

---

## Платежи

```
POST /api/payments/<booking_id>/
```

Создаёт платёж через ЮKassa, возвращает redirect на страницу оплаты.

---

## Статистика (админка)

```
GET /api/admin/stats/
```

```json
{
  "total_bookings": 42,
  "bookings_this_month": 15,
  "revenue_this_month": 45000.00
}
```

---

## HTML-страницы

| URL | Описание |
|---|---|
| `/` | Лендинг |
| `/service/` | Страница записи |
| `/service-finally/` | Подтверждение записи |
| `/notes/` | Мои записи (личный кабинет) |
| `/dashboard/` | Статистика (админ-панель) |
| `/admin/` | Django Admin |

---

## Модели (кратко)

| Модель | Назначение |
|---|---|
| `Salon` | Салон красоты |
| `Procedure` | Услуга/процедура |
| `ProcedureOffering` | Цена услуги в конкретном салоне |
| `Specialist` | Мастер |
| `SpecialistSalon` | Связь мастер → салон |
| `WorkShift` | Расписание (смена мастера) |
| `PromoCode` | Промокод (со скидкой) |
| `Booking` | Запись клиента |
| `CustomerProfile` | Профиль клиента |
| `ConsentDocument` | PDF-согласие |
| `ConsentAcceptance` | Принятие согласия |
| `SiteSettings` | Настройки (телефон менеджера) |

---

## Тестовые данные

```bash
python manage.py seed_db
```

Заполняет БД: 3 салона, 8 процедур, 24 ценовых предложения, 18 специалистов, 252 смены на 14 дней, 3 промокода.
Идемпотентно — можно запускать много раз, дубликатов не создаёт.

## Запуск

```bash
.venv\Scripts\python.exe manage.py runserver
```

# Code review BeautyCity — 2026-11-04

Ревью выполнено скиллом `code-review` из
[mattpocock/skills](https://github.com/mattpocock/skills): два параллельных
субагента, **Standards** и **Spec**.

- **Диапазон:** весь проект, `HEAD` против пустого дерева
  `4b825dc642cb6eb9a060e54bf8d69288fbee4904`.
- **Standards-ось:** `AGENTS.md` (Coding Conventions, Risks & Mitigations),
  `pyproject.toml` (`[tool.ruff]`), `README.md` + Fowler smell baseline.
- **Spec-ось:** `README.md` (§ «Что умеет сайт») и `AGENTS.md`
  (§ Key Features & User Flows, API Endpoints, Apps & Models, Risks).
  Отдельного issue tracker / spec-файла на момент ревью нет.
- **Состояние проекта на момент ревью:** uv + pre-commit настроены, тестов — 0.

> **Статус:** P0-1–P0-5 и P1-6–P1-12 закрыты.

## Как воспроизвести ревью

```bash
# окружение
uv sync
uv run pre-commit install

# скиллы (один раз, вне репозитория)
# см. docs/agent-skills.md

# diff, который смотрели
git diff 4b825dc642cb6eb9a060e54bf8d69288fbee4904 HEAD -- \
  apps beauty_city templates deploy README.md pyproject.toml manage.py \
  .github .pre-commit-config.yaml .gitattributes .gitignore
```

Затем в OpenCode вызвать `/code-review` и передать фиксированную точку
`4b825dc642cb6eb9a060e54bf8d69288fbee4904`.

## Приоритетный план

Чекбоксы отмечать по мере закрытия. Для каждого пункта указаны файлы и
критерий готовности.

### P0 — безопасность и деньги

- [x] **1. Закрыть вебхук ЮKassa.**
  Сейчас `@csrf_exempt` + доверие телу запроса: любой POST с
  `status: "succeeded"` подтверждает запись.
  Файл: `apps/core/payment_views.py:146`.
  Сделать: не доверять телу, а перезапрашивать платёж у ЮKassa по
  `payment_id` и проверять статус/сумму; либо проверять IP/подпись.
  Готово, когда поддельный POST не меняет статус, а настоящий — меняет.
  **Сделано:** вебхук перепроверяет платёж через `YooPayment.find_one()`,
  сверяет статус `succeeded`, сумму с `price_final` и metadata
  (`booking_id`/`booking_ids`). Подтверждение выполняется в
  `transaction.atomic()` с `select_for_update()`. Возврат с оплаты использует
  ту же проверку. Тесты: `apps/core/tests.py` (12 тестов на вебхук/оплату).

- [x] **2. Защита от двойной записи.**
  Сейчас `serializers.py` проверяет слот, затем `views.py` создаёт запись
  без транзакции и блокировки — два одновременных запроса проходят.
  Файлы: `apps/core/serializers.py:103`, `apps/core/views.py:132`.
  Сделать: `transaction.atomic()` + `select_for_update()` на пересекающиеся
  записи (или уникальное ограничение на `(specialist, start_at)`), учитывать
  длительность процедуры. Готово, когда параллельный тест создаёт ровно одну
  запись.
  **Сделано:** создание записи сериализовано через `UPDATE` строки
  `Specialist` (`booking_version`) — это работает и на SQLite, где
  `select_for_update()` не даёт блокировки. Внутри `transaction.atomic()`
  повторно проверяется пересечение интервалов (`is_slot_available()`), добавлен
  частичный `UniqueConstraint` на активные `(specialist, start_at)`, конфликт
  возвращает `409`. Тесты: `apps/core/tests.py` (включая параллельный
  сценарий).

- [x] **3. Авторизация `/api/my-bookings/`.**
  Сейчас отдаёт записи по `?phone=` без авторизации.
  Файл: `apps/core/views.py:214`.
  Сделать: `@login_required`/DRF permissions, телефон брать из
  `request.user`/`CustomerProfile`, параметр `phone` убрать.
  Готово, когда чужой телефон не отдаёт записи.
  **Сделано:** endpoint требует `IsAuthenticated`; телефон берётся через
  `get_user_phone()` (`CustomerProfile.phone`, затем `username` для старых
  phone-аккаунтов), `?phone=` игнорируется. Тот же helper используют `notes`,
  контекст-процессор и массовая оплата. Тесты: `apps/core/tests.py`
  (`MyBookingsAuthTests`, 5 тестов: без авторизации, только свои записи,
  игнорирование `?phone=`, профиль вместо username, fallback на username).

- [x] **4. Убрать тихий авто-логин после записи.**
  Сейчас `login_by_phone(request, booking.phone)` логинит без SMS-кода и даёт
  доступ к чужим записям/оплате.
  Файлы: `apps/core/views.py:156`, `apps/core/phone_auth.py:47`.
  Сделать: либо подтверждение кодом, либо отдельная сессия только для
  созданной записи. Готово, когда без кода нельзя открыть чужие записи.
  **Сделано:** после создания записи сессия не аутентифицируется; ID созданных
  записей сохраняются в `guest_booking_ids`. `notes` для гостя показывает
  только эти записи, а `create_payment` разрешает оплату только владельцу по
  телефону или гостевой сессии. После SMS-входа гостевой доступ очищается.
  Тесты: `apps/core/tests.py` (33 теста, включая отсутствие авто-логина,
  гостевые заметки и запрет оплаты чужой записи).

- [x] **5. Убрать `seed_db` и `ensure_admin` из продакшн-деплоя.**
  Файл: `.github/workflows/deploy.yml:34-35`.
  Сейчас каждый push в `main` создаёт демо-записи и сбрасывает пароль
  `Admin/Admin` (`apps/core/management/commands/ensure_admin.py:7`).
  Сделать: только `migrate` + `collectstatic`; сиды и админа — вручную или
  через отдельный одноразовый workflow. Готово, когда деплой не трогает данные.
  **Сделано:** `seed_db` и `ensure_admin` удалены из workflow; деплой теперь
  выполняет только `collectstatic` + `migrate`. Ручной запуск на VPS:
  `cd /var/www/beauty && uv run --frozen --no-dev python manage.py seed_db`,
  администратор — через `createsuperuser` (не `ensure_admin` с паролем по
  умолчанию).

### P1 — заявленные функции

- [x] **6. Промокоды.**
  Модель есть, логики нет: `promo_code` принимается, но цена не меняется.
  Файлы: `apps/core/views.py:150`, `apps/core/models.py` (`PromoCode`).
  Сделать: endpoint проверки (`/api/promo/check/` или DRF), расчёт
  `price_final` с учётом `discount_percent`, дат и аудитории; вывод скидки
  в форме и на подтверждении. Готово, когда валидный код уменьшает цену,
  невалидный — возвращает ошибку.
  **Сделано:** добавлен `POST /api/promo/check/` с проверкой активности и
  срока действия; при создании записи промокод валидируется и применяется к
  цене (`price_final = price_original * (100 - discount)/100`). Добавлен ввод
  промокода на странице подтверждения с отображением скидки. Тесты добавлены.

- [x] **7. Проверка «мастер делает услугу» и единая цена.**
  Сейчас проверяется только салон; подтверждение показывает
  `procedure.base_price`, а списывается `offering.price`.
  Файлы: `apps/core/serializers.py:117`, `apps/core/views.py:150`,
  шаблон `templates/serviceFinally.html`.
  Сделать: проверять `Specialist.procedures`/связь с процедурой и везде
  показывать `offering.price`.
  **Сделано:** добавлена проверка, что мастер выполняет выбранную процедуру;
  на фронте и в подтверждении используется цена из `ProcedureOffering`.

- [x] **8. Нормализация телефона.**
  `forms.py:clean_phone` не используется; API сохраняет телефон как есть,
  поэтому `notes`/`my_bookings` не находят номер в другом формате.
  Сделать: нормализовать телефон до сохранения и при поиске, переиспользовать
  `phone_validator`/`clean_phone`.
  **Сделано:** добавлен `normalize_phone()`; нормализация применяется в API
  создания записи, SMS-авторизации, профиле/поиске и формах.

- [x] **9. SMS-заглушка по README.**
  README обещает код в консоли, но `phone_auth.py:9` просто хранит `"1234"`
  без вывода, срока жизни и лимита попыток.
  Сделать: печатать код в консоль (или отдавать в dev-режиме), добавить
  `created_at`, TTL и лимит попыток.
  **Сделано:** код выводится в консоль, добавлены время создания, TTL и лимит
  попыток подтверждения.

- [x] **10. Отзывы, чаевые, отмена записи.**
  В спеке есть `POST /api/reviews/`, форма чаевых и отмена записи — сейчас
  модалки без обработчиков, endpoint'ов нет.
  Файлы: `templates/partials/_review_modal.html`,
  `templates/partials/_tips_modal.html`, `apps/core/urls.py`.
  Сделать: endpoint'ы + запись в `Review`/`Tip`, отмену — с проверкой прав.
  **Сделано:** добавлены `POST /api/reviews/`, `POST /api/tips/` и
  `POST /api/bookings/<id>/cancel/`; чаевые сохраняются в `Tip` (миграция),
  отзывы — в `Review`; отмена/чаевые доступны владельцу по телефону, гостевой
  сессии созданных записей или staff. Модалки и «Мои записи» подключены к
  endpoint'ам. Тесты добавлены.

- [x] **11. Статистика админки.**
  `visit_percentage` — заглушка `100`, `visits_month` считает будущие записи.
  Файл: `apps/core/views.py` (`admin_panel`).
  Сделать: реальный процент посещаемости или убрать показатель; считать
  только прошедшие подтверждённые визиты.
  **Сделано:** `visits_month`/`visits_year` считаются по прошедшим
  подтверждённым визитам (`start_at < now`, `CONFIRMED`);
  `visit_percentage` = доля подтверждённых среди прошедших (не отменённых)
  записей месяца, `0` если прошедших нет. Добавлен тест.

- [x] **12. Отзывы на лендинге из БД.**
  `templates/index.html` хардкодит отзывы, хотя модель `Review` есть.
  Сделать: передавать отзывы из view и рендерить в шаблоне.
  **Сделано:** `index` передаёт последние непустые отзывы из БД; лендинг
  рендерит их в слайдере отзывов. Добавлен тест.

### P2 — качество и сопровождение

- [x] **13. Убрать дублирование настроек:** `YOOKASSA_*` и `SITE_URL`
  объявлены дважды в `beauty_city/settings.py`.
  **Сделано:** оставлено одно определение с дефолтными значениями.
- [x] **14. Убрать дублирование сидов:** дубли логики смен/связок в командах
  сидирования; `seed_procedure_offerings.py` ссылался на несуществующую
  `seed_demo_data`.
  **Сделано:** `generate_shifts` и `seed_procedure_offerings` используют общие
  хелперы из `seed_db`; исправлены ссылки на `seed_db` в командах сидирования.
- [x] **15. Убрать дублирование `admin.py` и `forms.py`.**
  Дублировались `preview`/`preview_large` для Salon/Procedure/Specialist и логика
  нормализации телефона в форме.
  **Сделано:** добавлен `ImagePreviewAdminMixin`; `forms.py` использует общий
  `normalize_phone()` (P1-8).
- [x] **16. Убрать дублирование шаблонов.**
  Карточки записей в `notes.html` (предстоящие/прошедшие) дублировались.
  **Сделано:** добавлен `templates/partials/_notes_booking_card.html` с
  вариантом `upcoming`/`past`; `notes.html` использует общий partial при
  сохранении классов, data-атрибутов, URL и JS-хуков (`rewiewPopupOpen`,
  `tipsPopupOpen`, `notes__cancelBtn`). Сайдбары `notes.html`/`admin.html`
  оставлены раздельно: отличаются по авторизации/гостевому режиму, имени и
  пунктам меню — параметризация давала бы больше сложности, чем пользы.
- [x] **17. Использовать `Booking.Status.CONFIRMED`/`CANCELED`** вместо строк
  статусов в Python-коде (`payment_views.py`, `views.py`).
  **Сделано:** оставшиеся строковые сравнения/фильтры в `views.py` заменены на
  константы `Booking.Status.*`; в `payment_views.py` уже использовались константы.
- [~] **18. Удалить мёртвый код или реализовать.**
  **Сделано (безопасно):** удалён неиспользуемый `BookingForm`.
  **Оставлено/уточнено:** `ConsentDocument`/`ConsentAcceptance` используются в
  моделях/админке/сидах (поток сохранения согласия — отдельное решение);
  `SiteSettings` используется в админке/сидах; `Booking.discount_percent` — не
  мёртвое поле, а используемое свойство (процент из `promo_code`), в отличие от
  устаревшей формулировки ревью. Удаление моделей/полей требует миграций и
  продуктового решения.
- [x] **19. Почистить `seed_db.py`:** `data.pop("image")`/`avatar` мутировал
  модульные константы, сиды нельзя было вызвать дважды.
  **Сделано:** сиды читают `image`/`avatar` без мутации и исключают их из
  `defaults` при `get_or_create`.
- [x] **20. Убрать Middle Man:** `views.py:176` `initiate_payment` повторно
  достаёт booking и делегирует в `create_payment`, который достаёт его снова.
  **Сделано в P0-4:** `initiate_payment` сразу делегирует в `create_payment`.
- [x] **21. Обновить `AGENTS.md`.**
  Структура `accounts/salons/...`, `Appointment`, Celery/Redis/`Notification`,
  VK/email-auth не соответствовали коду.
  **Сделано локально:** `AGENTS.md` приведён к фактической структуре
  (`apps/core`), стеку, доменным правилам, командам и ограничениям
  безопасности/деплоя. Файл игнорируется `.gitignore`, поэтому в git не
  коммитится.
- [~] **22. Добавить тесты.** Сейчас 45 тестов покрывают вебхук/оплату,
  создание записи, конфликт слотов, защиту от двойной записи, авторизацию
  `/api/my-bookings/`, гостевой доступ после записи, промокоды, отзывы, чаевые,
  отмену записи, статистику админки и отзывы на лендинге (`apps/core/tests.py`).
  Остаются edge cases и покрытие оставшихся P2 сценариев.

## Standards — полный отчёт

### Hard violations (documented standards)

**`AGENTS.md` → «Risks & Mitigations: Двойная запись → `select_for_update()` +
проверка пересечения слотов»**
`apps/core/views.py:150` создаёт запись без транзакции и блокировки; единственная
защита — read-then-write проверка слота в `apps/core/serializers.py:125-130`:

```python
slots = get_available_slots(..., date=date)
if time not in slots:
    raise serializers.ValidationError(f"Время {time} уже занято")
```

Два одновременных POST оба проходят. Нет `transaction.atomic()`, нет
`select_for_update()`, нет DB-ограничения на `(specialist, start_at)`.

**Статус:** закрыто в P0-2 — добавлены блокировка строки мастера, повторная
проверка пересечения в транзакции и частичный уникальный индекс.

**`AGENTS.md` → «Промокоды → полная логика + валидация»**
`promo_code` принимается, но не используется: `views.py:150-153` сохраняет
`price_original=offering.price, price_final=offering.price`.
`Booking.discount_percent` (`models.py:293`) — мёртвое поле. `/api/promo/check/`
отсутствует. **Исправлено в P1-6:** промокоды проверяются и скидка применяется.

**`AGENTS.md` → «Project Structure» / «Apps & Models»**
Один `apps/core` вместо `accounts/ salons/ bookings/ payments/ promos/ reviews/
notifications`; `Procedure`/`Specialist`/`Booking` вместо
`Service`/`Master`/`Appointment`; статусы `canceled` без `completed`.
README описывает новую структуру, поэтому AGENTS.md устарел — judgement call,
но расхождение нигде не зафиксировано.

### Judgement calls (baseline smells)

- **Duplicated Code** — `beauty_city/settings.py:15-17` повторяет
  `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`, `SITE_URL` из `:89-91`; первый
  блок мёртвый.
- **Duplicated Code** — `generate_shifts.py:29-48` и `seed_db.py:430-448` —
  один и тот же цикл смен; `seed_procedure_offerings.py` повторяет
  `seed_offerings` и предлагает несуществующую команду `seed_demo_data`.
- **Duplicated Code** — `admin.py:45-70` трижды повторяет
  `preview`/`preview_large` для Salon/Procedure/Specialist;
  `forms.py:59-73` заново реализует `models.phone_validator`.
- **Duplicated Code** — `templates/notes.html:90-148` и `155-209`: карточка
  записи ~100 одинаковых строк; сайдбар кабинета скопирован в
  `admin.html:12-60`.
- **Primitive Obsession / Repeated Switches** — строковый `"confirmed"` вместо
  `Booking.Status.CONFIRMED` в `payment_views.py:27,71,133,142,160,168`,
  `views.py:188,252`; `request.user.username` использовался как телефон, хотя
  есть `CustomerProfile.phone` (`views.py:220`, `payment_views.py:85`).
  **Статус:** телефонная часть закрыта в P0-3 через `get_user_phone()`;
  строковые статусы остаются.
- **Divergent Change** — `context_processors.py:19-20` пишет `user.first_name`
  на каждом рендере, дублируя backfill в `views.py:158-160`.
- **Middle Man** — `views.py:176-178` `initiate_payment` только повторно
  достаёт booking и делегирует в `create_payment`, который достаёт его снова.
- **Speculative Generality** — никогда не вызываются: `BookingForm`,
  `ConsentAcceptance`, `SiteSettings`, `Booking.discount_percent`.
  `index.html:110-181` хардкодит отзывы, хотя `Review` существует.
- **Deploy risk** — `deploy.yml:34-35` запускает `seed_db` и `ensure_admin`
  (хардкод `Admin/Admin`, `ensure_admin.py:7`) на продакшене.
- **Mysterious Name** — `seed_db.py:380` мутирует модульные константы через
  `data.pop("image")`, поэтому `seed_salons()` нельзя вызвать дважды в одном
  процессе.

## Spec — полный отчёт

**Spec sources:** `README.md` (§ «Что умеет сайт», «Вход в личный кабинет») и
`AGENTS.md` (§ Key Features & User Flows, API Endpoints, Apps & Models,
Risks & Mitigations). Устаревшая структура `accounts/salons/...` в AGENTS.md
сама по себе не считается провалом.

### (a) Missing / partial

- **Промокоды отсутствуют.** AGENTS: *«Клиент вводит код → сервер проверяет
  (тип, дата, существование)… → пересчёт цены»*, `POST /api/promo/check/`.
  Есть только модель и админка; нет endpoint, UI и расчёта скидки.
- **Чаевые отсутствуют.** AGENTS: *«Чаевые (форма → запись в базу)»*, модель
  `Tip`. `_tips_modal.html` — `<form action="#">` без обработчика и бэкенда.
- **Создание отзыва.** AGENTS: `POST /api/reviews/`. Endpoint отсутствует;
  кнопка «Оставить отзыв» открывает ту же мёртвую модалку; отзывы на лендинге —
  хардкод 2022 года.
- **Отмена записи.** AGENTS Dev-2: *«Создание/отмена записей»* — есть только
  создание.
- **Reminders (Flow 5) / Celery, `Notification`, VK/email auth** — удалены в
  `4b91558`, но остались в AGENTS.md.
- **SMS-заглушка.** README: *«код печатается в консоль сервера»* — ничего не
  печатается; `phone_auth.py:9 TESTING_CODE = "1234"`, код не истекает и не
  имеет лимита попыток.

### (b) Not asked for

- Массовая оплата «Оплатить всё» (`pay-all-unpaid`) — README просит только
  *«Оплачивает запись онлайн»*.
- Тихий авто-логин после записи (`views.py:156`) — нет основания в спеке.
  **Исправлено в P0-4:** после записи создаётся только гостевая сессия на
  созданные записи, полный вход — после SMS-кода.
- `ConsentDocument`/`ConsentAcceptance` и обязательные чекбоксы, но согласие
  нигде не сохраняется.
- Деплой запускает `seed_db` и `ensure_admin` на каждый push в `main`:
  демо-записи на продакшене и сброс пароля `Admin/Admin`.
- `/api/admin/stats/` (публичный, не используется UI); `SiteSettings.manager_phone`
  не используется.

### (c) Implemented but wrong

- README: *«посещаемость»* — `views.py:267 "visit_percentage": 100  # Заглушка`;
  `visits_month` считает будущие записи текущего месяца посещениями.
- AGENTS: *«Двойная запись -> select_for_update() + проверка пересечения»* —
  проверка слота без блокировки; конфликты считаются по `(salon, specialist)`,
  поэтому мастер может быть занят в двух салонах одновременно. Исправлено в
  P0-2: блокировка мастера + проверка пересечения без привязки к салону.
- AGENTS: `GET /api/client/appointments/` — фактический
  `/api/my-bookings/?phone=` не требует авторизации и отдаёт записи по любому
  телефону. **Исправлено в P0-3:** endpoint требует авторизацию, `?phone=`
  игнорируется, телефон берётся из профиля пользователя.
- `yookassa_webhook` — `csrf_exempt` без проверки подписи/IP: любой POST со
  `status:"succeeded"` подтверждает запись.
- Авто-логин по телефону из формы даёт доступ к чужим записям и оплате без
  SMS-кода. **Исправлено в P0-4:** авто-логин убран, гостевая сессия ограничена
  созданными записями, оплата проверяет доступ.
- `forms.py:clean_phone` не используется; API сохраняет телефон как есть,
  поэтому `notes`/`my_bookings` не находят неотформатированные номера.
- Сервер принимает специалиста, который не выполняет выбранную процедуру
  (проверяется только салон); страница подтверждения показывает
  `procedure.base_price`, а списывается `offering.price`.

## Итог

- **Standards:** 13 findings (3 hard + 10 judgement). Худшее — отсутствие
  защиты от двойной записи (закрыто в P0-2).
- **Spec:** 18 findings. Худшее — вебхук ЮKassa без проверки подписи позволяет
  подтвердить оплату без оплаты (закрыто в P0-1).

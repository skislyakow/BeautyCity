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

- [ ] **1. Закрыть вебхук ЮKassa.**
  Сейчас `@csrf_exempt` + доверие телу запроса: любой POST с
  `status: "succeeded"` подтверждает запись.
  Файл: `apps/core/payment_views.py:61`.
  Сделать: не доверять телу, а перезапрашивать платёж у ЮKassa по
  `payment_id` и проверять статус/сумму; либо проверять IP/подпись.
  Готово, когда поддельный POST не меняет статус, а настоящий — меняет.

- [ ] **2. Защита от двойной записи.**
  Сейчас `serializers.py` проверяет слот, затем `views.py` создаёт запись
  без транзакции и блокировки — два одновременных запроса проходят.
  Файлы: `apps/core/serializers.py:103`, `apps/core/views.py:132`.
  Сделать: `transaction.atomic()` + `select_for_update()` на пересекающиеся
  записи (или уникальное ограничение на `(specialist, start_at)`), учитывать
  длительность процедуры. Готово, когда параллельный тест создаёт ровно одну
  запись.

- [ ] **3. Авторизация `/api/my-bookings/`.**
  Сейчас отдаёт записи по `?phone=` без авторизации.
  Файл: `apps/core/views.py:166`.
  Сделать: `@login_required`/DRF permissions, телефон брать из
  `request.user`/`CustomerProfile`, параметр `phone` убрать.
  Готово, когда чужой телефон не отдаёт записи.

- [ ] **4. Убрать тихий авто-логин после записи.**
  Сейчас `login_by_phone(request, booking.phone)` логинит без SMS-кода и даёт
  доступ к чужим записям/оплате.
  Файлы: `apps/core/views.py:156`, `apps/core/phone_auth.py:47`.
  Сделать: либо подтверждение кодом, либо отдельная сессия только для
  созданной записи. Готово, когда без кода нельзя открыть чужие записи.

- [ ] **5. Убрать `seed_db` и `ensure_admin` из продакшн-деплоя.**
  Файл: `.github/workflows/deploy.yml:34-35`.
  Сейчас каждый push в `main` создаёт демо-записи и сбрасывает пароль
  `Admin/Admin` (`apps/core/management/commands/ensure_admin.py:7`).
  Сделать: только `migrate` + `collectstatic`; сиды и админа — вручную или
  через отдельный одноразовый workflow. Готово, когда деплой не трогает данные.

### P1 — заявленные функции

- [ ] **6. Промокоды.**
  Модель есть, логики нет: `promo_code` принимается, но цена не меняется.
  Файлы: `apps/core/views.py:150`, `apps/core/models.py` (`PromoCode`).
  Сделать: endpoint проверки (`/api/promo/check/` или DRF), расчёт
  `price_final` с учётом `discount_percent`, дат и аудитории; вывод скидки
  в форме и на подтверждении. Готово, когда валидный код уменьшает цену,
  невалидный — возвращает ошибку.

- [ ] **7. Проверка «мастер делает услугу» и единая цена.**
  Сейчас проверяется только салон; подтверждение показывает
  `procedure.base_price`, а списывается `offering.price`.
  Файлы: `apps/core/serializers.py:117`, `apps/core/views.py:150`,
  шаблон `templates/serviceFinally.html`.
  Сделать: проверять `Specialist.procedures`/связь с процедурой и везде
  показывать `offering.price`.

- [ ] **8. Нормализация телефона.**
  `forms.py:clean_phone` не используется; API сохраняет телефон как есть,
  поэтому `notes`/`my_bookings` не находят номер в другом формате.
  Сделать: нормализовать телефон до сохранения и при поиске, переиспользовать
  `phone_validator`/`clean_phone`.

- [ ] **9. SMS-заглушка по README.**
  README обещает код в консоли, но `phone_auth.py:9` просто хранит `"1234"`
  без вывода, срока жизни и лимита попыток.
  Сделать: печатать код в консоль (или отдавать в dev-режиме), добавить
  `created_at`, TTL и лимит попыток.

- [ ] **10. Отзывы, чаевые, отмена записи.**
  В спеке есть `POST /api/reviews/`, форма чаевых и отмена записи — сейчас
  модалки без обработчиков, endpoint'ов нет.
  Файлы: `templates/partials/_review_modal.html`,
  `templates/partials/_tips_modal.html`, `apps/core/urls.py`.
  Сделать: endpoint'ы + запись в `Review`/`Tip`, отмену — с проверкой прав.

- [ ] **11. Статистика админки.**
  `visit_percentage` — заглушка `100`, `visits_month` считает будущие записи.
  Файл: `apps/core/views.py:257-267`.
  Сделать: реальный процент посещаемости или убрать показатель; считать
  только прошедшие подтверждённые визиты.

- [ ] **12. Отзывы на лендинге из БД.**
  `templates/index.html:110-181` хардкодит отзывы, хотя модель `Review` есть.
  Сделать: передавать отзывы из view и рендерить в шаблоне.

### P2 — качество и сопровождение

- [ ] **13. Убрать дублирование настроек:** `YOOKASSA_*` и `SITE_URL`
  объявлены дважды в `beauty_city/settings.py:15-17` и `:89-91`.
- [ ] **14. Убрать дублирование сидов:** `generate_shifts.py:29-48` и
  `seed_db.py:430-448`; исправить `seed_procedure_offerings.py`, который
  ссылается на несуществующую `seed_demo_data`.
- [ ] **15. Убрать дублирование `admin.py:45-70`** (`preview`/`preview_large`
  для Salon/Procedure/Specialist) и `forms.py:59-73` (копия `phone_validator`).
- [ ] **16. Убрать дублирование шаблонов:** карточки в `notes.html:90-209`,
  сайдбар в `admin.html:12-60`.
- [ ] **17. Использовать `Booking.Status.CONFIRMED`** вместо строк
  `"confirmed"` (`payment_views.py`, `views.py`).
- [ ] **18. Удалить мёртвый код или реализовать:** `BookingForm`,
  `ConsentAcceptance`/`ConsentDocument` (согласие не сохраняется),
  `SiteSettings`, `Booking.discount_percent`.
- [ ] **19. Почистить `seed_db.py:380`:** `data.pop("image")` мутирует
  модульную константу, `seed_salons()` нельзя вызвать дважды.
- [ ] **20. Убрать Middle Man:** `views.py:176` `initiate_payment` повторно
  достаёт booking и делегирует в `create_payment`, который достаёт его снова.
- [ ] **21. Обновить `AGENTS.md`:** структура `accounts/salons/...`,
  `Appointment`, Celery/Redis/`Notification`, VK/email-auth — уже не
  соответствуют коду. Либо актуализировать, либо удалить устаревшие разделы.
- [ ] **22. Добавить тесты.** Сейчас `python manage.py test` находит 0 тестов.
  Минимум: создание записи, конфликт слотов, промокод, вебхук, доступ к
  `/api/my-bookings/`.

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

**`AGENTS.md` → «Промокоды → полная логика + валидация»**
`promo_code` принимается, но не используется: `views.py:150-153` сохраняет
`price_original=offering.price, price_final=offering.price`.
`Booking.discount_percent` (`models.py:293`) — мёртвое поле. `/api/promo/check/`
отсутствует.

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
  `views.py:188,252`; `request.user.username` используется как телефон, хотя
  есть `CustomerProfile.phone` (`views.py:220`, `payment_views.py:85`).
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
  поэтому мастер может быть занят в двух салонах одновременно.
- AGENTS: `GET /api/client/appointments/` — фактический
  `/api/my-bookings/?phone=` не требует авторизации и отдаёт записи по любому
  телефону.
- `yookassa_webhook` — `csrf_exempt` без проверки подписи/IP: любой POST со
  `status:"succeeded"` подтверждает запись.
- Авто-логин по телефону из формы даёт доступ к чужим записям и оплате без
  SMS-кода.
- `forms.py:clean_phone` не используется; API сохраняет телефон как есть,
  поэтому `notes`/`my_bookings` не находят неотформатированные номера.
- Сервер принимает специалиста, который не выполняет выбранную процедуру
  (проверяется только салон); страница подтверждения показывает
  `procedure.base_price`, а списывается `offering.price`.

## Итог

- **Standards:** 13 findings (3 hard + 10 judgement). Худшее — отсутствие
  защиты от двойной записи.
- **Spec:** 18 findings. Худшее — вебхук ЮKassa без проверки подписи позволяет
  подтвердить оплату без оплаты.

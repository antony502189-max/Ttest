# Проверка Stripe sandbox — 13 октября 2026

Проверялся локальный проект `C:\Users\HONOR\Documents\Codex\Ttest`, Docker-проект `ttest-stripe-test`. Производственный сайт и производственная база данных не использовались. Во всех обращениях к Stripe применялся существующий `sk_test_` ключ; значение ключа не выводилось. Реальные денежные операции не выполнялись.

## Что именно оплачивается

В проекте интегрирована **Stripe Hosted Checkout**. В платёжном коде нет бронирования жилья или оплаты аренды. Покупаются:

| Покупка | Цена, определяемая backend | Результат подтверждения |
|---|---|---|
| TOP объявления на 1 день | 100 евроцентов = 1 € | Продвижение на 1 день |
| TOP на 7 дней | 500 евроцентов = 5 € | Продвижение на 7 дней |
| TOP на 30 дней | 1000 евроцентов = 10 € | Продвижение на 30 дней |
| Реклама на 30 дней | `ADVERTISEMENT_30D_PRICE_CENTS`, локально 3000 = 30 € | `paid` / `pending_review`, затем отдельная модерация |

Поэтому сценарий «выбрать жильё → забронировать → оплатить аренду» к текущему коду неприменим. Добавление такого процесса потребовало бы отдельной разработки и определения бизнес-правил.

Frontend: React 19, TypeScript, Vite, React Router HashRouter, Tailwind. Backend: Python 3.12+, FastAPI, SQLAlchemy async, asyncpg, Alembic. База: PostgreSQL 16 / PostGIS. Redis используется инфраструктурой приложения. Для этого стенда файлы хранятся локально, почта отправляется в Mailpit; MinIO и внешние импортёры для проверки платежей не нужны. Stripe SDK не установлен: интеграция вызывает HTTPS API через `httpx`.

## Файлы и прохождение платежа

- `backend/app/api/v1/payments.py`: создание заказов, проверка владельца и пакета, webhook, выдача оплаченной услуги.
- `backend/app/services/stripe_checkout.py`: запросы к Stripe и проверка подписи уведомлений.
- `backend/app/models/payment_order.py`: таблица `payment_orders`.
- `backend/alembic/versions/0057_payment_orders.py`: миграция этой таблицы.
- `backend/app/core/config.py`: ключи, секрет webhook, запрет live-ключей без явного включения.
- `backend/app/models/moderation.py`: сроки и суммы TOP в `listing_promotions`.
- `backend/app/models/commercial_advertisement.py`: состояние рекламной кампании.
- `src/pages/AccountPages.tsx`: выбор TOP, запрос checkout, переход через `window.location.assign`.
- `src/pages/CommercialAdvertisementPages.tsx`, `src/api/commercial-advertisements.ts`: рекламный checkout, переход, чтение статуса кампании. После возврата реклама опрашивается каждые 3 секунды в течение 30 секунд.
- `backend/app/api/v1/commercial_advertisements.py`: старый локальный fake-payment endpoint; он возвращает 404 при настроенном Stripe и в production. Это имитация, не sandbox Stripe.
- `docker-compose.stripe-test.yml`, `.env.stripe-test.local`, `scripts/set-stripe-test-secrets.ps1`, `docs/stripe-local-sandbox.md`: отдельный локальный стенд.

Пользователь отправляет авторизованный POST:

```text
/api/v1/payments/listings/{listing_id}/top/checkout
/api/v1/payments/advertisements/{ad_id}/checkout
```

Backend блокирует строку объекта в БД, проверяет владельца и допустимый статус, определяет цену и создаёт `payment_orders` со статусом `pending`. В Stripe отправляется `POST https://api.stripe.com/v1/checkout/sessions`, `mode=payment`, EUR, одна позиция товара и серверная сумма. Идентификатор заказа передаётся как `client_reference_id` и `metadata.order_id`; он же используется как `Idempotency-Key`. Backend сохраняет ID сессии и Checkout URL. Frontend получает URL и переходит на сайт Stripe. Карточные данные не отправляются в backend проекта.

Stripe возвращает браузер на `http://localhost:5173/#/...?...`. Параметры `payment=return` и `payment=cancelled` — только параметры навигации, не подтверждение оплаты.

Подтверждение приходит на `POST /api/v1/payments/stripe/webhook`. Подпись HMAC SHA-256 проверяется по исходным байтам тела; допускается отклонение времени до 300 секунд. Для успешного события проверяются ID заказа и Stripe-сессии, сумма, валюта EUR, `livemode` и `payment_status=paid`. Заказ блокируется на время обработки; повторное событие для `paid` повторно услугу не начисляет. Изменения заказа и услуги сохраняются одним commit.

## Результаты и доказательства

Здесь различаются три вида проверки:

1. **Автоматические тесты с mock:** Stripe и SQLAlchemy session заменены имитациями. Они проверяют код, но не подтверждают настоящий платёж.
2. **Реальный PostgreSQL + синтетические события:** обработчик выполняет настоящий SQL; события и подписи созданы локально. Внешняя транзакция отменяет все изменения после проверки.
3. **Настоящий Stripe sandbox API / CLI:** запросы и события реально существуют у провайдера, `livemode=false`.

| Проверка | Результат | Комментарий |
|---|---|---|
| Создание платежа | Успешно | Авторизованный HTTP POST локального backend создал настоящий sandbox TOP checkout на 1 € и заказ в БД. Клиентские `amountCents=1`, `currency=USD`, `status=paid` не изменили параметры заказа. |
| Успешная оплата | Успешно | Подтверждена ранее созданная sandbox-реклама: Stripe GET 200, `status=complete`, `payment_status=paid`, EUR, 3000, `livemode=false`. Новый ввод карты в этом аудите не завершён. Старый заказ восстановлен ручным replay настоящего события. Автоматическая доставка успешного события заново не доказана. |
| Отклонение платежа | Не проверено | Тестовая карта в доступной для ввода форме не была отправлена; отказ провайдера не получен. Синтетическое `payment_status=unpaid` услугу не выдаёт. |
| Отмена платежа | Не проверено | Нажатие Cancel/Back в браузере не завершено. Отдельно реально проверено закрытие неоплаченной Checkout-сессии через sandbox API: `expired`, `unpaid`; в БД `expired`, без `paid_at`. |
| Получение webhook | Успешно | Настоящий `checkout.session.expired`, событие `evt_1UQB9nQhTBxdX4Ui9MxNhW92`, доставлено Stripe CLI; локальный endpoint ответил HTTP 200 и обновил заказ. Успешный платёж обработан ручным replay, а не автоматической доставкой. |
| Обновление базы данных | Успешно | Реклама `paid` / `pending_review`; закрытый TOP `expired`. Синтетический успешный TOP записал срок и сумму; изменения этого теста отменены. |
| Защита от повторной оплаты | Успешно | Два одновременных HTTP запроса возвращают одну URL и создают один заказ. Повтор настоящего успешного события вручную не изменил `paid_at`. Повтор TOP не добавил дней в проверках с БД. Завершённая сессия без webhook блокирует новый checkout в автоматическом тесте. |
| Безопасность интеграции | Не проверено | Полный аудит безопасности не выполнен. Пройденные проверки: подпись и её срок, подмена суммы/валюты/режима/ID, чужие объекты через реальные SQL-фильтры, HTTP 401 без авторизации, HTTP 400 без подписи, запрет live-ключа, отсутствие Stripe-секретов в src/public/dist. |

**29 автоматических тестов пройдены.** Запущены исходные `test_stripe_checkout.py` и новые `test_stripe_payment_boundaries.py`. До исправлений на коде старого контейнера 10 тестов воспроизвели проблемы структуры события и первоначальной суммы TOP. После всех исправлений — `29 passed`.

`npm run typecheck` завершился с кодом 0. Проверка frontend на `localhost:5173` получила HTTP 200 и подтвердила подставленный адрес sandbox API `localhost:18000/api/v1`.

Новый автоматический браузер открыл настоящий Checkout и увидел интерфейс sandbox, но не смог завершить взаимодействие с карточной формой: загрузка была медленной, наблюдались отменённые запросы hCaptcha и таймаут видимости кнопки карточной оплаты. CAPTCHA не обходилась. Это ограничение выполненной проверки; точная причина недоступности формы не установлена.

### Найденное расхождение и восстановление

При первом чтении БД старая реклама за 30 € имела `payment_orders.status=pending`. Stripe уже сообщала `paid` и содержала настоящее событие `evt_1UQ8cqQhTBxdX4UinTPDog7b`. Процесс Stripe CLI отсутствовал, в просмотренных последних 200 строках локальных логов webhook не найден. Отсутствие работающей доставки согласуется с расхождением, но короткая выборка логов не доказывает всю историю доставки.

Установлен CLI 1.53.1 в игнорируемый `.stripe-tools/cli-runtime`; его signing secret совпал с текущим секретом backend. Listener подключён к sandbox и реально доставил последующее событие истечения с HTTP 200.

Старое событие получено непосредственно из API Stripe и повторно отправлено на локальный обработчик. **Его содержимое настоящее, новая HMAC подпись и доставка созданы локально вручную.** Это восстановление данных, а не проверка автоматической доставки Stripe. После replay заказ стал `paid`, реклама `paid` / `pending_review`. Повторный replay оставил `paid_at` неизменным. Нового списания не было.

## Исправления

1. **Некорректная структура webhook:** подписанные JSON-массивы, null и неправильные `data.object` могли приводить к исключениям вместо контролируемого ответа. Добавлены проверки структуры в `stripe_checkout.py` и `payments.py`; теперь HTTP 400, без изменения заказа.
2. **Первый TOP не сохранял общую сумму:** при создании `ListingPromotion` поле `total_price_cents` оставалось NULL; повторное продление учитывало только последующие покупки. Теперь первоначальная сумма записывается. Уже существующие строки массово не переписывались.
3. **Истечение сессии игнорировалось:** добавлена обработка `checkout.session.expired` с теми же проверками ID, суммы, валюты, режима и подписи. `pending` становится `expired`; `paid` никогда не понижается. Создание новой сессии после истечения остаётся отдельным запросом пользователя.
4. **Повторно выдавалась устаревшая/завершённая URL до 25 часов:** backend теперь читает настоящий статус сохранённой сессии через Stripe GET. `open` переиспользуется, `expired` разрешает замену, `complete` без локального подтверждения возвращает 409 «ожидает подтверждения; не оплачивайте повторно». Недоступность Stripe возвращает 502, без создания нового заказа. Это добавляет один запрос к Stripe при повторной попытке.
5. **Ложный текст подтверждения рекламы:** интерфейс показывал «оплата подтверждена» для любого статуса кампании, отличного от `pending_payment`, в том числе отменённой неоплаченной кампании. В `CommercialAdvertisementPages.tsx` этот текст теперь требует `paymentStatus=paid` и `status=pending_review`; в остальных случаях выводится статус кампании. Проверка TypeScript пройдена.

Цена пакетов, модерация рекламы и правила допуска объявления к TOP не менялись. Миграции для исправлений не требуются.

Исправленные файлы скопированы в работающий локальный sandbox-контейнер и backend перезапущен; автоматические тесты выполнялись по этим файлам. Исходники сохранены в репозитории. **Копирование в контейнер не пересобирает Docker-образ:** при следующем создании контейнера используйте `--build` либо существующий cached-image override с подключением актуального исходного кода.

## Практические шаги на Windows

### Шаг 1: проверить окружение

**Зачем:** убедиться, что команды обращаются к отдельному стенду.

**Действие:** в PowerShell из корня проекта:

```powershell
Set-Location C:\Users\HONOR\Documents\Codex\Ttest
docker compose version
docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml ps
Invoke-WebRequest http://127.0.0.1:18000/health/ready
```

**Ожидаемый результат:** PostgreSQL, Redis и backend healthy; `/health/ready` — HTTP 200.

**Проверка:** имена контейнеров начинаются с `ttest-stripe-test`; API — порт 18000, база — 15432. Другой локальный Docker-проект `ttest` найден, но его unhealthy backend на 8000 не исправлялся: он не является стендом этого аудита.

**Если возникнет ошибка:** сначала запустите Docker Desktop. В агентском sandbox PATH отличался от обычного пользователя; исполняемый Docker находится по адресу `C:\Users\HONOR\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe`. Можно использовать `& 'полный путь'` вместо `docker`. При отсутствии ключей не запускайте `docker compose config` с выводом всей конфигурации: она раскрывает значения переменных.

### Шаг 2: конфигурация sandbox

**Зачем:** настроить серверные секреты и адреса.

**Действие:** использовать существующий `.stripe-test.secrets`. Если ключи нужно заменить, открыть нужную песочницу Stripe → Developers/API keys и выполнить:

```powershell
powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\set-stripe-test-secrets.ps1
```

**Ожидаемый результат:** `STRIPE_SECRET_KEY` имеет префикс `sk_test_`, `STRIPE_WEBHOOK_SECRET` — `whsec_`; `STRIPE_LIVE_PAYMENTS_ENABLED=false` задан в Compose. Файл секретов игнорируется Git и доступен текущему пользователю.

**Проверка:** ключи не передаются в VITE-переменные. Фронтенду нужны только `VITE_API_BASE_URL=http://localhost:18000/api/v1` и `VITE_ENABLE_MOCK_MODE=0`, уже заданные в `.env.stripe-test.local`. Backend также получает DATABASE_URL, REDIS_URL, JWT_SECRET, FRONTEND_APP_URL/ORIGINS, SMTP, STORAGE_BACKEND и MEDIA_ROOT из отдельного Compose. Publishable Stripe key frontend не нужен: используется готовая hosted URL.

**Если возникнет ошибка:** при рассогласовании секретов webhook будет HTTP 400. Секрет локального CLI и секрет отдельного Dashboard webhook endpoint не взаимозаменяемы. Не отправляйте ключи в чат и не передавайте их аргументами команды.

### Шаг 3: держать доставку webhook работающей

**Зачем:** Stripe не может напрямую обратиться к localhost.

**Действие:** для обычного ручного запуска после `stripe login`:

```powershell
.\.stripe-tools\cli-runtime\node_modules\@stripe\cli-win32-x64\bin\stripe.exe listen --skip-update --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.expired,checkout.session.async_payment_failed --forward-to http://127.0.0.1:18000/api/v1/payments/stripe/webhook
```

**Ожидаемый результат:** `Ready`, затем строки события и ответа HTTP 200.

**Проверка:** CLI работает в нужной песочнице и backend использует secret именно этого listener. Во время аудита listener запущен с ключом через `STRIPE_API_KEY` в окружении процесса; значение ключа и secret в логах скрыты. Обычный повторный запуск без авторизации CLI требует `stripe login` и проверки выбранного аккаунта. Уже работающий listener не нужно дублировать.

**Если возникнет ошибка:** HTTP 400 — проверьте secret, тело и идентификатор заказа; 5xx — backend/БД; отсутствие события — аккаунт/режим/подключение CLI. Для данного стенда ngrok не нужен: CLI пересылает события без публичного endpoint. При использовании отдельного туннеля потребуются публичный HTTPS endpoint в Dashboard и его собственный webhook secret.

### Шаг 4: запуск с актуальным исходным кодом

**Зачем:** сделать исправления частью следующего запуска контейнера.

**Действие:**

```powershell
docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml up -d --build postgres redis mailpit migrate backend
npm run dev -- --mode stripe-test --host localhost --strictPort
```

**Ожидаемый результат:** frontend `http://localhost:5173/#/`, backend 18000. Миграция 0057 применена; mock mode выключен.

**Проверка:** на этом компьютере frontend уже работает на 5173; второй экземпляр запускать не нужно. Mailpit доступен на `http://127.0.0.1:18025` для локальной почты. В sandbox-сборке API docs: `http://127.0.0.1:18000/api/docs`.

**Если возникнет ошибка:** strictPort сообщает о занятом порте — используйте уже запущенный frontend. При недоступности npm в PATH: `& .\.stripe-tools\node-v24.21.0-win-x64\npm.cmd run dev -- --mode stripe-test --host localhost --strictPort`. Если сборка зависимостей недоступна, существующий `docker-compose.stripe-test.cached-image.yml` подключает текущий backend-код к локальному образу; это запасной путь для разработки, не выпускной образ.

### Шаг 5: оставшиеся браузерные сценарии

**Зачем:** завершить проверки, которые нельзя заменить API-запросом или mock.

**Действие:** открыть новую Checkout-сессию, отправленную в панель браузера этого чата, либо войти в локальный сайт как владелец и выбрать TOP в «Mis anuncios». Проверить отметку sandbox и сумму **1 €**. Старая сессия, закрытая в аудите, больше не оплачивается.

Для успеха: карта `4242 4242 4242 4242`, будущая дата, например 12/34, любой трёхзначный CVC. Для отказа: `4000 0000 0000 0002`. Для 3DS: `4000 0025 0000 3155`; проверить успешное и отменённое подтверждение. Используйте только эти тестовые данные; реальные карты не нужны.

**Ожидаемый результат:** при успехе Stripe показывает завершение, CLI — `checkout.session.completed` и HTTP 200, заказ — `paid`, TOP получает срок. При отказе Stripe показывает понятную ошибку; заказ не становится `paid`. При Back/Cancel возвращается приложение, услуга не начисляется. Простое закрытие вкладки обычно оставляет сессию открытой и заказ `pending` до реального истечения; это не доказательство ошибки оплаты и не событие успешного платежа.

**Проверка:** до и после каждого сценария читать БД:

```powershell
docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml exec -T postgres psql -U ttest -d ttest_stripe -c "SELECT kind, days, amount_cents, status, paid_at FROM payment_orders ORDER BY created_at DESC LIMIT 10;"
docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml exec -T postgres psql -U ttest -d ttest_stripe -c "SELECT listing_id, starts_at, ends_at, total_price_cents FROM listing_promotions ORDER BY starts_at DESC LIMIT 5;"
docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml exec -T postgres psql -U ttest -d ttest_stripe -c "SELECT status, payment_status FROM commercial_advertisements ORDER BY created_at DESC LIMIT 5;"
```

**Если возникнет ошибка:** paid в Stripe и pending в БД означает проблему подтверждения, не повод снова платить. Проверить webhook и при необходимости выполнить ручное восстановление ниже. Если форма Stripe требует человеческую проверку или не загружается, завершить её в обычном браузере, не обходя защиту. Для разных пакетов до завершения текущей покупки используйте разные объявления.

### Шаг 6: воспроизведение диагностики

**Зачем:** повторить проверку без имитации итогов.

**Действие:**

```powershell
# Реальная PostgreSQL, синтетические события, полный rollback:
Get-Content .\scripts\stripe-sandbox-db-audit.py -Raw | docker exec -i ttest-stripe-test-backend-1 python -

# Настоящее создание sandbox checkout через авторизованный HTTP и два одновременных запроса:
# Создаёт тестовый заказ; временная QA-сессия входа отзывается в finally.
Get-Content .\scripts\stripe-sandbox-create-checkout.py -Raw | docker exec -i ttest-stripe-test-backend-1 python -

# Ручное восстановление только уже оплаченных sandbox заказов по настоящим событиям API:
# Записывает реальные статусы в локальную БД; это ручной replay с локальной подписью.
Get-Content .\scripts\stripe-sandbox-reconcile.py -Raw | docker exec -i ttest-stripe-test-backend-1 python -
```

**Ожидаемый результат:** скрипты отказываются работать без `sk_test_`, при включённых live-платежах или с БД, отличной от `ttest_stripe`. DB-аудит печатает PASS и ROLLBACK. Reconcile оставляет неоплаченные сессии без изменений.

**Проверка:** 29 unit-тестов запускались в sandbox-контейнере через временную установку pytest/pytest-asyncio в `/tmp/stripe-audit-deps`; этот каталог не является частью образа. Для стандартной среды разработчика установить `backend[dev]` в отдельное Python окружение и запустить из backend:

```powershell
python -m pytest -q tests/test_stripe_checkout.py tests/test_stripe_payment_boundaries.py
```

**Если возникнет ошибка:** скрипту БД нужны локальные неоплаченная реклама и опубликованное внутреннее объявление. Не заменяйте DATABASE_URL производственным адресом. Для работы скриптов внутри контейнера нужен актуальный `/app/app`.

## Что осталось перед реальными платежами

- Завершить новую успешную покупку с автоматическим `checkout.session.completed`, отказ картой и Cancel/Back в обычном браузере; проверить 3DS.
- Проверить задержанные способы оплаты. Сейчас `checkout.session.async_payment_failed` не устанавливает отдельный статус отказа и не уведомляет пользователя; доступные способы оплаты выбирает конфигурация аккаунта Stripe, код не ограничивает их только картой.
- Настроить надёжную production-доставку webhook, мониторинг ошибок и регулярную сверку зависших заказов. Созданный reconciliation script предназначен только для локального sandbox, не для production.
- Разобрать позднюю оплату локально `expired` заказа: текущий обработчик фиксирует `paid`, пишет ошибку в лог и не выдаёт услугу автоматически. Аналогично оплаченные удалённые/отменённые объекты и legacy TOP без срока требуют ручного рассмотрения. Автоматического возврата средств нет.
- UI отмены/отказа не полноценно отражает отдельный статус платежа. Ложный текст подтверждения рекламной кампании исправлен; полный UX отказа и отмены ещё требуется проверить.
- Отдельно проверить откат/недоступность БД, задержки провайдера, доставку вне порядка и конкуренцию успешного webhook с новым checkout. В этом аудите не выполнялось нагрузочное тестирование Stripe.
- Настроить production-цены, HTTPS и отдельные секреты после завершения sandbox-проверок. Флаг live-платежей в этой работе не включался.

**Вывод:** стенд готов к дальнейшему sandbox-тестированию. Создание Checkout, серверная цена, повторные запросы, подтверждение в БД и настоящая доставка события истечения проверены с доказательствами. Полный браузерный набор сценариев ещё не завершён; готовность к реальным платежам не подтверждена.

Официальные источники: [тестовые карты Stripe](https://docs.stripe.com/testing), [локальная доставка webhook](https://docs.stripe.com/webhooks), [срок Checkout-сессии](https://docs.stripe.com/api/checkout/sessions/create), [API закрытия сессии](https://docs.stripe.com/api/checkout/sessions/expire).

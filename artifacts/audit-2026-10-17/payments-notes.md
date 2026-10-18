# Аудит платежей и TOP: подтвержденные результаты

Проверен `15b673864c28ec90c85e78f4cb37eedadfe982c2`. Production code не менялся. Stripe HTTP заменен тестовыми провайдерами; настоящие платежи и production credentials не использовались. Изолированная PostgreSQL/PostGIS БД `audit_payment_extra` находится в audit-контейнере на `127.0.0.1:55439`; миграции до head применены. Общая тестовая БД родительского аудитора не затрагивалась.

Итог этой части аудита: **2 подтвержденных P1, 1 подтвержденный P2; P0/P3 не зарегистрированы**. Обычная покупка последнего места и дубли webhooks защищены, однако полный инвариант «максимум три TOP» нарушается альтернативным административно-финансовым путем. Рекомендация по платежной части: **NOT READY FOR RELEASE**.

## Исполненные проверки

- `payment/test_payment_audit_probes.py`: **5 passed**, 1.00s, точные production функции с замоканными persistence/Stripe.
- `payment/integration/test_payment_routes.py`: **8 passed**, 13.05s, настоящие PostgreSQL транзакции и API через ASGI; замокан только Stripe. **Три теста намеренно подтверждают дефекты**, поэтому зеленый результат не означает корректность продукта.
- Лог последнего API-прогона: `payment/routes-run.log`.
- Машиночитаемое доказательство overbooking: `payment/overbooking-evidence.json`.
- Первоначальный API-прогон имел 6 passed / 1 failed из-за ошибки нового audit-теста: использовано `Notification.kind` вместо существующего `Notification.type`. Audit-тест исправлен; приложение не менялось. Финальный прогон 8/8 указан выше.
- Пять warnings `PytestUnknownMarkWarning` относятся к переиспользуемым integration helper-модулям: запуск вне backend pytest root не подхватывает декларацию marker. Это не ошибки приложения.
- В restricted Windows sandbox создание `asyncio` event loop зависало в `socket._fallback_socketpair -> accept`; faulthandler подтвердил инфраструктурную причину. Изолированные тесты выполнены с одобренным `require_escalated`, после чего завершились нормально.

Команда финального API-прогона, рабочая директория `backend` (учетные данные ниже исключительно синтетические для новой audit-БД):

```powershell
$env:APP_ENV='test'
$env:DATABASE_URL='postgresql+asyncpg://audit:audit@127.0.0.1:55439/audit_payment_extra'
$env:REDIS_URL=''
$env:STORAGE_BACKEND='local'
$env:MEDIA_ROOT='../artifacts/audit-2026-10-17/payment/media'
$env:PYTHONPATH='C:\Users\HONOR\Documents\Codex\Ttest\backend'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
& 'C:\Users\HONOR\Documents\Codex\Ttest\output\release-venv\Scripts\python.exe' -u -m pytest '../artifacts/audit-2026-10-17/payment/integration/test_payment_routes.py' -vv -p pytest_asyncio.plugin -p no:cacheprovider -o asyncio_mode=auto -o asyncio_default_fixture_loop_scope=session -o asyncio_default_test_loop_scope=session
```

Для mock-based проверок путь к файлу заменить на `../artifacts/audit-2026-10-17/payment/test_payment_audit_probes.py`; отдельная БД для них не нужна.

## PAY-001 — Финансовый refresh повторно активирует четвертый оплаченный TOP

**Severity:** P1. **Уверенность:** высокая, воспроизведено через реальные API и PostgreSQL, подтверждено публичным search API.

**Location:** `backend/app/services/payment_finances.py:123` и `:154`; связанный административный entry point `backend/app/services/admin.py:357`.

**Проблема:** проверка capacity в `change_service_finances()` выполняется только для `fulfillment_status == "review_required"`. Ниже агрегированный `ListingPromotion` заново строится из всех действующих fulfilled/normal `PaymentOrder` без проверки, расширяет ли это фактическую видимость по сравнению с нынешним окном. Admin PUT может перед этим сократить строку promotion, сохранив order.fulfillment_status=fulfilled. Старое entitlement восстанавливается финансовым событием поверх трех новых проданных мест. PostgreSQL advisory lock сериализует этот путь, но не защищает пропущенное бизнес-условие.

**Воспроизведение:**

1. Создать объявление с postcode `28013`, оплатить TOP на 30 дней; order=paid/fulfilled/normal, `payment_intent` задан уже в первом успешном Checkout webhook.
2. Через авторизованный `PUT /api/v1/admin/listings/{id}/promotion` сократить `endsAt` до текущего времени + 2 секунды. Ответ 200; оплаченный order по-прежнему fulfilled.
3. После истечения сокращенного promotion три других владельца покупают и оплачивают TOP в той же provinceCode=`28`. Все три покупки возвращают 200.
4. Доставить подписанный `charge.dispute.closed`, при котором авторитетный Stripe test double возвращает dispute.status=`won`, исходный charge не refunded, order еще fulfilled/normal. Это допустимое поступление первой финансовой нотификации после окончания спора: доставка предыдущего created может отсутствовать/запаздывать.
5. `change_service_finances()` восстанавливает старый 30-дневный promotion и пропускает проверку capacity.

**Ожидается:** максимум три одновременно действующих места; либо восстановление первого order уходит на review без активации, либо административное сокращение оплаченного срока выполняется через согласованную financial resolution и уже не может автоматически отмениться.

**Получено:** **4** текущих `ListingPromotion` и **4** `promoted=true` в `POST /api/v1/listings/search` с `provinceCode=28`. HTTP financial webhook 200. JSON evidence:

```json
{"provinceCode":"28","databaseActiveTopCount":4,"publicSearchPromotedCount":4,"signedFinancialEventType":"charge.dispute.closed","disputeSnapshotStatus":"won"}
```

**Влияние:** прямое нарушение главного клиентского ограничения, продажа неэксклюзивного TOP четырем покупателям, финансовые претензии. Для воспроизведения нужны обычная admin-операция и штатное финансовое событие; не требуется подделать подпись Stripe, выполнить параллельные запросы или изменить production БД вручную.

**Минимальное исправление:** перед любым увеличением/возобновлением фактического promotion относительно сохраненного окна под тем же capacity lock проверять полный resulting interval, независимо от старой метки fulfilled. Не допускать независимого сокращения/удаления Stripe-managed TOP через legacy admin-проекции: согласовывать order и promotion в одной операции. При недостатке capacity — review_required без расширения окна и явная операторская компенсация.

**Regression:** сохранить сценарий `test_confirmed_admin_shortening_then_normal_financial_event_overbooks`, изменив ожидаемый результат на <=3 и явный review/refund исходного order; дополнительно проверить первый доставленный `dispute.closed=won`, повторные normal snapshots, расширение из будущего интервала и перемещение в другую провинцию после admin removal.

## PAY-002 — Admin удаляет оплаченный TOP, а restore ложно сообщает успех

**Severity:** P1. **Уверенность:** высокая, API + PostgreSQL.

**Location:** `backend/app/services/admin.py:385`, `:395`; перезапись окна `:357`; ложный idempotent success в `backend/app/services/payment_finances.py:277`.

**Проблема:** legacy admin DELETE/PUT `promotion` не проверяет paid/pending orders и не синхронизирует их fulfillment. DELETE удаляет сам entitlement projection, оставив paid order fulfilled/normal. Так как review queue фильтрует только review_required, платеж не попадает на разбор. Операторский restore сразу возвращает resolved=true на fulfilled/normal, не проверяя наличие фактического promotion.

**Воспроизведение:** оплатить TOP30d; авторизованным admin вызвать `DELETE /api/v1/admin/listings/{id}/promotion`; запросить `/payments/admin/review-required`; затем `/payments/admin/orders/{order}/resolve` с action=restore и валидной reason.

**Ожидается:** отказ удалить незавершенную покупку, либо управляемая отмена с review/refund, либо настоящее восстановление entitlement. Финансовое состояние обязано соответствовать предоставляемой услуге.

**Получено:** DELETE 200, promotion отсутствует; order paid/fulfilled/normal, service_ends_at в будущем; review queue пустая; resolve 200 с `resolved:true`, но promotion после restore все еще отсутствует. Повторный успешный checkout webhook также не обязан восстановить строку: idempotent paid-ветка возвращает раньше fulfillment.

**Влияние:** покупатель теряет оплаченный период, обычный операторский интерфейс показывает успешную услугу/восстановление. Также исчезнувшая строка освобождает TOP capacity и перестает блокировать смену провинции, хотя оплаченный order еще действует; это усиливает риск повторного несогласованного восстановления.

**Исправление:** запретить legacy PUT/DELETE для незавершенного Stripe-managed entitlement либо направить их в общий audited pause/cancel/refund lifecycle. При административном снятии сохранять order.review_required и причину, не терять service history. Early-return restore допустим только после проверки существования и соответствия entitlement проекции; иначе выполнять восстановление с capacity check.

**Regression:** `test_confirmed_admin_delete_loses_paid_top_without_review` должен ожидать controlled409 или согласованное review; отдельно проверить PUT сокращение/замену периода, pending checkout, повторное restore и отсутствие ложного resolved=true.

## PAY-003 — Дневная TOP-оплата активируется после блокировки владельца

**Severity:** P2. **Уверенность:** высокая, API + PostgreSQL и отдельный production-function probe.

**Location:** `backend/app/services/payment_fulfillment.py:137-138`; полный критерий уже существует в `backend/app/services/homepage_purchase.py:23-36`; публикация исключает владельца в `backend/app/repositories/listings.py:311-314`.

**Проблема:** новое `/top/checkout` продает `days` и создает order без `duration_months=1`. Поэтому fulfillment идет в ветку `else`, где проверяются лишь published/is_external/deleted_at самого listing. Полная функция `eligible()` вызывается только для legacy monthly TOP. Ее проверки текущей блокировки/удаления owner, пользовательских/listing restrictions, действующей фотографии и допустимой цены пропускаются. На initiation эта функция вызывается, но состояние может измениться до платежа.

**Воспроизведение:** корректное опубликованное объявление -> TOP checkout -> блокировка User и UserRestriction.publish в изолированной БД (эквивалент изменения moderation state во время provider checkout) -> подписанный successful Checkout callback.

**Ожидается:** после оплаты повторно проверить актуальную публичную eligibility; при невозможности оказать услугу сохранить paid/review_required и предложить resolution/refund.

**Получено:** promotion создан и order fulfilled, хотя владелец blocked; notification сообщает успешный TOP. Публичный `visible_query` исключает такого владельца, поэтому оплаченная услуга реально не видна. Это не обход публичной moderation: ошибка состоит в несогласованной оплате/fulfillment и невидимом расходовании capacity.

**Исправление:** использовать единый полный eligible для daily и monthly fulfillment; при отрицательном результате обычный review_required путь уже реализован. Согласовать owner-block/listing restriction с политикой уже действующих покупок.

**Regression:** блокировка owner, активная listing/user restriction, удаление медиа и изменение цены между checkout и successful callback; проверить отсутствие promotion и наличие paid/review_required.

## Матрица обязательных payment scenarios A–J

Все статусы относятся только к указанной выполненной части и не отменяют PAY-001/002.

| Scenario | Статус | Исполненное доказательство / предел |
|---|---|---|
| A: двое за последний TOP | PASS в ordinary checkout | Настоящие concurrent HTTP requests при двух оплаченных местах: [200,409], 3 orders/3 promotions. Не означает защиту от PAY-001. |
| B: успех после expiry reservation | PASS по безопасности, ручной review | Provider-confirmed expired освобожден, 3 других TOP проданы; поздний paid callback -> paid/review_required, promotion отсутствует, четвертого места нет. Автоматический refund этим сценарием не проверен. |
| C: repeated success webhook | PASS | Три concurrent callbacks + повторные delivery оставляют единственный effective grant; число notifications не увеличивается. |
| D: browser закрыт после оплаты | PASS для backend recovery | Нет redirect/status visit/webhook: worker process_advertising_alerts получает paid remote state и создает entitlement. Живой браузер не требовался и не проверялся. |
| E: direct API при full province | PASS для ordinary checkout | После 3 active TOP direct checkout четвертого ->409; provinceB отдельно имеет3slots и покупает независимо. |
| F: TOP истекает во время обработки новой покупки | NOT VERIFIED полностью | Исполнено контролируемое истечение DB promotion и следующий availability: slots0->1; отсутствие background cleanup не мешает. Точная interleaving expiry/Stripe IO здесь отдельно не воспроизведена. |
| G: изменение province/address | PASS для прямой owner mutation | Active и pending TOP: PATCH postcode28013->08001 ->409. Внутри province разрешено политикой; административный обход после removal связан с PAY-002. |
| H: crash между оплатой и activation | PASS для rollback/retry | Искусственный exception ровно перед fulfillment commit; БД остается pending/no promotion; retry callback затем duplicate ->ровно1promotion. Также worker восстанавливает отсутствующую webhook-доставку. Hard process kill отдельного сервера не выполнялся. |
| I: concurrent workers одного event | PASS на уровне независимых API DB sessions | asyncio.gather трех signed callbacks, настоящие PostgreSQL row/advisory locks; ровно1effective grant. Несколько отдельных OS processes не запускались. |
| J: rapid payment requests same item | PASS | Два simultaneous checkout повторения используют один Checkout URL/PaymentOrder; всего3 provider sessions на3успешных reservation. Тестовый provider deterministic по order UUID; реальный Stripe idempotency transport здесь замокан. |

Дополнительно исполнено: availableSlots 3/2/1/0 для0/1/2/3 TOP; независимость province28/08; активный и pending TOP не могут менять postcode; expiry capacity вычисляется по timestamp без cleanup job.

## Как реализованы платежи и блокировки

1. `payments.py` считает цену сервером: TOP100 cents/day при10..365 днях; homepage hero6000 cents/calendar month; bottom advertisement3000 cents/calendar month. Нельзя передать произвольную сумму. Owner-bound запросы, require_admin для resolution.
2. Все обычные capacity mutations используют **один PostgreSQL transaction advisory lock** `commercial-advertising:homepage-bottom` (`commercial_advertisements.py:19-23`), включая TOP разных провинций и hero. Это cross-instance lock, а не process-local mutex. Он не создает constraint на capacity в БД: пропущенная проверка остается опасной, как PAY-001.
3. Order со status=creating и reservation сохраняется **до** Stripe POST (`payment_sessions.py:18-21`). Внешний IO выполняется после commit, поэтому provider latency не держит global advisory lock. Stripe idempotency key=order UUID; finalize повторно берет lock/refresh order.
4. `province_top.py:51-65`: promotions и creating/pending orders фильтруются по province, вычисленной из listing.postcode. Reservation бессрочна локально до авторитетного provider-state; несколько окон одного listing считают одну capacity единицу. Scheduled windows учитываются при проверке полного приобретаемого интервала; renewal исключает собственное listing из конкурентов.
5. Signed webhook проверяет HMAC/timestamp, amount integer/exact, EUR, live/test environment, session/order association; paid-путь и expiration-путь разделены. Затем advisory lock + order FOR UPDATE обеспечивают effective idempotency в стандартном fulfillment (`payment_fulfillment.py:44-72`). Success redirect не дает entitlement.
6. Listing TOP хранит агрегированную projection и отдельные service intervals в PaymentOrder; refund/dispute bookkeeping сохраняет service history и имеет durable inbox. Refunds суммируются по авторитетным succeeded receipts, full refunds/chargeback lost приводят к revoked; pending/partial требуют review. Эти детали просмотрены статически; полный refund suite выполняет родительский аудитор.
7. Bottom banner ограничен7, hero1; правило3 TOP не применяется к ним. Fake payment endpoints возвращают404 при production/настроенном Stripe (`api/v1/commercial_advertisements.py:288-305`).
8. Active TOP-address смена блокируется сервером, в том числе у sibling listings при `syncAddressGroup` (`listings.py:148-149`, `:577-578`).

## Риски и ограничения, НЕ выдаваемые за подтвержденные security bugs

- **Неизвестный результат создания checkout:** любой неуспех Stripe transport оставляет order.creating; после23h finish_creation добавляет review_required, сохраняя creating и capacity reservation (`payment_sessions.py:13-17`, `province_top.py:58-65`). Это выполненный mock probe и сознательный conservative safe failure: локально нельзя объявлять платеж несуществующим после network timeout. Но3таких attempts способны блокировать провинцию до оператора. Если provider однозначно отказал без создания session, система не отличает это от неизвестного исхода; operator reconcile требует реальный sessionID. Нужны документированный verified-abandon workflow/метрики и отдельная обработка доказуемых rejection, без опасного автоматического release по локальному TTL. Уязвимость unpaid privilege или overbooking из этого не заявляется.
- TOP Checkout, в отличие от banner/hero, не ограничивается card/31мин (`stripe_checkout.py:52`): стандартная provider expiry может удерживать места существенно дольше, а async methods требуют корректной обработки финального paid/failed. Это продуктовая/операционная политика, не само по себе финансовая уязвимость.
- Ограничение3 не является DB check/unique-slot invariant. Оно зависит от вызова проверки во всех путях. Admin и financial projection rebuild — доказанные исключения.
- При legacy>3 промо код запрещает новые покупки до снижения count, но не исправляет уже существующий oversubscription. Нужна отдельная сверка реальной мигрированной БД; аудит production records не проводился.
- Резервы после рестарта сохранены в PostgreSQL, локальная cache не источник правды — статически обосновано; настоящий restart server/container с активной услугой в этой подзадаче не выполнялся.
- Истечение и current time проверялись сервером; JS countdown, client skew, responsive UI и визуальная эквивалентность входят в другую часть аудита.
- Live Stripe и настоящий network idempotency не проверялись. Официальный `allowed_payment_method_types` **валиден** в актуальном Checkout create API; это не баг: [Stripe Checkout Session create](https://docs.stripe.com/api/checkout/sessions/create), параметр описан как dynamic filter. Проверка выполнена web17.10.2026, без платежей.

## Приоритет исправления

1. P1: сделать paid TOP lifecycle единым для admin, finance и обычного checkout; запрещать несогласованные mutation projection, проверять capacity перед каждым фактическим расширением. Добавить PAY-001 regression с реальной PostgreSQL.
2. P1: убрать ложное resolved=true, если оплаченный promotion отсутствует; снятие модерацией должно попадать на review/refund и сохранять возможность безопасного restore.
3. P2: одинаковая eligibility в daily/monthly fulfillment.
4. Добавить реальную PostgreSQL acceptance matrix для expiry interleaving, restoration after province move, restart и transient Stripe failures; не ограничиваться mock-тестами SQL query shape.


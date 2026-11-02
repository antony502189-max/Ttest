# Пункт 2: функциональная приёмка закрытого стенда

Использовать только worktree `C:\Users\HONOR\.codex\worktrees\main-integration-audit\Ttest`,
ветку `codex/post-merge-remediation` и локальный стенд пункта 1.
Реальные UI/API/PostGIS/Redis; конечный тестовый parser и synthetic extraction.
Не включать реальные providers, ASR, уведомления или public AI. Merge запрещён.

## Воспроизведение

```powershell
./scripts/ai-text-lab.ps1 start
node scripts/accept-ai-text-lab.mjs
node scripts/smoke-ai-text-lab.mjs
node scripts/check-ai-text-lab-isolation.mjs
./scripts/ai-text-lab.ps1 status
./scripts/ai-text-lab.ps1 stop
```

Start требует committed source. Основной приёмочный runner сам загружает новый
набор через настоящий FactPipeline → facts/projections → QueryProofs.prepare.
Результаты и 9 screenshots: `output/ai-text-acceptance/`. При падении добавляются
URL/текст synthetic страницы и screenshot. Не подставлять browser API responses.
В сценариях потери ответа `route.fetch()` сначала вызывает настоящий backend
до commit, затем браузер теряет доставку этого ответа через `route.abort()`.

Runner уважает существующие технические Redis gates/Retry-After, не меняет
business quota и не обнуляет дневные counters. Несколько полных повторов тратят
квоту synthetic auth account; перед большим числом повторов проверить remaining.
Существующие/shared и capacity DB не нужны. Старые объявления и raw evidence
пункта 1 не изменяются.

## Отдельный приёмочный каталог

Семь новых **holiday** объявлений, свой host и account
`acceptance-user@synthetic.example`, пароль `Synthetic-Lab-Only-2026!`.
Эти локальные тестовые значения не подходят для других окружений.
Original long fixtures остаются на месте, прежний smoke с long возвращает 4/2/1.
В БД всего 14 listings; базовый seed допускает только точный зарегистрированный
набор из исходных 7 либо исходных 7 + этих 7, без произвольного расширения.

| Имя | ID | EUR/night | Pets | Balcony |
|---|---|---:|---|---|
| a | c980e2ea-6073-5507-bb6a-a4e48a8b39b8 | 50 | allow | true |
| b | 397e1206-3792-59ad-8a4c-bd9890ab74c7 | 55 | allow | true |
| c | 03214bd5-6611-5989-8b6c-a917cb7d04ea | 60 | allow | false |
| d | 99c9e46f-25b8-5e90-89da-40f65918c128 | 45 | deny | true |
| e | 331f5203-ccca-507a-9138-bddefbe05f2b | 50 | unknown | unknown |
| f | d59d00fb-cd80-5422-adfd-d2c2feee7748 | 70 | allow | true |
| g | 5e8fed84-f84d-5832-8ebf-5b143f74660b | 80 | allow | unknown |

На главной открыть AI и выбрать «Sin limitar el modo de alquiler». Ввести
`туризм`: parser ставит hard rental_mode=holiday. Получатся 7 карточек,
6 на первой странице и 1 на второй; назад должны вернуться те же 6 IDs.
`с маленькой собакой` → 5 (a,b,c,f,g), затем `до 60 евро за ночь` → 3 (a,b,c).
Карта того же committed result должна содержать эти 3 IDs.

Другие проверки: `все варианты` снимает всё кроме rental_mode;
`желательно с балконом` не исключает unknown и даёт 7; замена на
`обязательно с балконом` даёт 4 (a,b,d,f). Добавление small dog даёт 3 (a,b,f),
`до 40 евро за ночь` — 0. Для более трёх успешных сообщений нужен auth account:
guest имеет прежние 3/сутки, auth — 200/сутки Europe/Madrid.

## Ручная матрица

| Проверка | Действия | Ожидаемое поведение |
|---|---|---|
| Обычный поиск | Вернуться к фильтрам, выбрать long и прежние условия | Прежний manual API/маршрут; AI критерии туда не добавляются |
| Hard/soft/unknown | Выполнить последовательности выше | Совпадают IDs/counts; unknown не превращается в allow |
| Страницы и карта | Вперёд/назад, затем открыть карту, pan/zoom | Нет дублей/пропусков, карта привязана к result_ref/intent_hash |
| Reload | Выполнить запрос и перезагрузить страницу | Session/result читаются заново у сервера, quota не меняется |
| Mobile reload | При повторном onboarding пройти язык/страну/privacy и «Сейчас нет» | После возвращения открыть AI; owned result восстанавливается |
| Уточнение | После reload добавить nightly budget | Новая версия typed intent; pets и rental_mode сохраняются |
| Текущий и прежний intent | Получить новый result, затем читать старый result_ref | Старые cards используют старые committed conditions, editable session — новые |
| Чужие ссылки | В другом guest context подставить session/result UUID | Нет карточек и доступа к чужой сессии; сервер отказывает |
| Потеря доставки | Оборвать доставку query/create/reset после реального ответа backend | Тот же idempotency key/body; тот же результат/session; один parser call/debit |
| Одновременный дубль | Отправить одну operation дважды во время parser delay | Один запрос в ledger; второй читает running/terminal, без повторного parser |
| Конфликт | Изменить payload с тем же key либо отправить новый key со старой version | Idempotency conflict / failed SESSION_VERSION_CONFLICT; без лишнего debit |
| Ошибка parser | Однократно включить failure на model boundary | Failed, used не увеличивается, повтор того же key не вызывает parser |
| Отмена server task | Однократно включить cancel на model boundary | Reservation released, used=0; exact retry читает failed |
| Прекратить ожидание | Delay → «Прекратить ожидание» → проверить тот же запрос | Обрыв ожидания не обещает rollback уже принятой операции; завершённая операция списывается ровно один раз |
| Истечение | Expire собственную test session; page/reload/replay | Cards недоступны, новый поиск только явно; durable receipt не списывает снова |
| Смена source/цены/moderation/visibility | Изменить g между страницами | g отсутствует до count/page/map; stale cursor требует повторного чтения |
| Нет proof | Удалить proof a и попытаться продолжить страницу | Старые неподтверждённые карточки скрыты, paging заблокирован; диалог не подменён |
| Ошибка восстановления | Потерять ответ GET session после reload, затем повторить | UUID locators сохраняются; retry восстанавливает данные, без нового поиска/debit |
| Размеры и языки | ES/EN/RU × 320/768/1440 px | Нет горизонтального overflow; conditions, cards и карта доступны |

## Локальные fault controls

Контроллер проверяет purpose label контейнера, backend проверяет точные
destinations и marker dedicated DB. Это CLI на компьютере владельца,
**не HTTP admin endpoint**. Допустимы только перечисленные synthetic fixtures
и явно переданные test session IDs; не применять expire/arm к ручной сессии пользователя.

```powershell
node scripts/ai-text-lab-control.mjs seed
node scripts/ai-text-lab-control.mjs change g source
node scripts/ai-text-lab-control.mjs change g price
node scripts/ai-text-lab-control.mjs change g proof       # после смены цены: prepared=false
node scripts/ai-text-lab-control.mjs change g moderation
node scripts/ai-text-lab-control.mjs change g hidden
node scripts/ai-text-lab-control.mjs change a missing
node scripts/ai-text-lab-control.mjs change a restore
node scripts/ai-text-lab-control.mjs change g restore
node scripts/ai-text-lab-control.mjs inspect <session-uuid> <expected-version>
node scripts/ai-text-lab-control.mjs arm <session-uuid> <expected-version> delay
node scripts/ai-text-lab-control.mjs arm <session-uuid> <expected-version> failure
node scripts/ai-text-lab-control.mjs arm <session-uuid> <expected-version> cancel
node scripts/ai-text-lab-control.mjs expire <session-uuid>
```

Delay фиксирован 3 s, faults одноразовые, Redis TTL 60 s. Call counters содержат
только session UUID/version, живут 2 h; текст сообщений не записывается.
Restore возвращает только соответствующий новый fixture, затем проходит
настоящую подготовку proof. Не вставляет готовый proof SQL-строкой.
В конце runner восстанавливает семь новых fixtures и истекает только собранные
им test sessions; дневную quota, исходные fixtures и receipts не удаляет.

Продолжение после reload хранит только session UUID/result UUID в sessionStorage,
с отдельным ключом для guest/auth identity. Ни текст, ни criteria/cards, ни
tokens не сохраняются. Pending request text после reload автоматически не
восстанавливается и не отправляется; это сохраняет прежнюю privacy boundary.
Реальная модель, capacity/quality, policy/retention и release остаются этапами 3–8.

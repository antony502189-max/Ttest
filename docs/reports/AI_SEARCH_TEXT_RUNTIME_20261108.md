# S2.1 / S3.2 — подключение текстового runtime, 08.11.2026

База — настоящий `origin/main` `afdf180c922da65de8f0fbdf3e89005e30faf481`.
Application source: `23419bfb251d99d856194a2e199f4d49eb69cbc9`.
Работа в existing worktree, отдельная ветка `codex/ai-search-text-runtime`.
Изменения PR409 не входят в application diff этого increment; ждать его merge не нужно.
Root checkout не переключался, чужие изменения сохранены.

**Работающего LIVE демо ещё нет.** Изменение соединяет существующие компоненты
в приложении вне test-only lab и устанавливает обязательный startup lifecycle.
Оно не создаёт разрешённый provider adapter, AI-проекции реальных объявлений
или демонстрационную среду. Ни UI→модель→SQL, ни работа на выпущенном сайте
этой проверкой не подтверждены.

## Что изменилось

`app.services.ai_text_runtime.assemble_text_runtime` собирает существующие
`AISearchRuntime`, `TextSearchExecution`, `QuotaLedger`, owned `SearchSessions`,
`VerifiedCardSearch`, `GuestTokens`, distributed Redis HTTP/attempt/inflight gates.
SQL-карточки и карта используют прежние proof/currentness/freshness guards.
Словари intent берутся из того же `FactPipeline`; source TTL обязателен.
Cursor key отделён от всех guest verification keys. Parser deadline должен
помещаться в execution deadline, тот — в HTTP deadline.

`install_text_runtime(app, runtime)` публикует capabilities только после:

1. Обычного application startup.
2. Проверки application schema `0079_ai_operating_policy` (старую production0066
   нельзя объявить совместимой аргументом запуска).
3. Успешного Redis ping.
4. Загрузки существующего настроенного deletion journal и `replay_erasure`,
   который проверяет его DB binding и завершает принятые удаления.

При ошибке runtime не публикуется; при shutdown убирается, Redis закрывается.
Установка не заменяет существующий runtime. Явный kill switch через снятие
`app.state.ai_search_runtime` сразу закрывает прежние HTTP routes.

Импорт/сборка не включают AI, не открывают provider, не делают миграций,
не инициализируют journal, не создают фактов и не запускают сбор объявлений.
`app.main` по умолчанию остался выключенным. Deployment должен передать
отдельно разрешённый parser и pipeline, затем вызвать installer в собственной
явной factory; существующий `maintain_ai_search --loop` требует отдельного
supervisor. Само наличие этих функций не является готовой конфигурацией выпуска.

## Настоящий сервер и каталог: только чтение

SSH с существующим ключом и strict host verification подтвердил hostname
`vmi3640228`, `/srv/112233.es/current` и public `build-info.json`:
deployed SHA `1292c6807ece59999238bb31c80e09ef7e2c3212`.
Это не текущий main. БД — `0066_complimentary_ads`; таблиц `ai_*` нет.
Public `/api/v1/ai-search/capabilities` не ответил успешно; статус HTTP не был
сохранён, поэтому конкретный код ошибки не заявляется.

Выполнены aggregate SQL в `REPEATABLE READ READ ONLY`, statement timeout5s,
без экспорта записей, raw payload, контактов, credentials или персональных данных.
Публичный знаменатель взят из **существующего `visible_query()`**, включая
ценовой cap и owner/moderation restrictions. Не добавлялся самодельный expiry
predicate: отдельная предварительная диагностическая проверка с
`expires_at > now()` дала0, но это не predicate приложения и не знаменатель отчёта.

Срез08.11 01:30MSK: **1439 публичных карточек**, **132** проходят отдельный
source health/freshness≤24h guard. **132 — не AI verified coverage**: AI-таблиц
на этом сервере пока нет. Проверенное наличие источника не подтверждает все
свойства объявления или возможность бронирования.

Срез08.11 01:35MSK по тому же public/source predicate:

| Источник | Свежий public subset | Цена≤600€/мес | Цена≤400€/мес | С public approximate location |
| --- | ---: | ---: | ---: | ---: |
| AlquilerDocenteCanarias | 9 | 9 | 4 | 9 |
| Habitaclia | 94 | 6 | 1 | 0 |
| PisoCompartido | 12 | 11 | 3 | 12 |
| Pisos | 17 | 16 | 6 | 17 |

Цены здесь — текущие stored card values, не результаты inference или принятые
AI proofs. Habitaclia не подходит для обещания карты: adapter сознательно
не считает page viewport координатами объекта. Предлагаемый первый небольшой
cohort — существующий public PisoCompartido subset (до20 записей, сейчас12),
без нового crawling/backfill. Его source-specific price/evidence mapping и
подготовка proof на изолированной копии **ещё нужны**; snapshot быстро стареет.

Raw aggregate evidence: [inventory](ai-text-runtime-20261108-evidence/production-inventory.json),
[demo candidates](ai-text-runtime-20261108-evidence/demo-candidates.json).
Оба содержат query hashes, DB timestamps и только агрегаты.

## Проверки и их предел

Новые10 unit cases проверяют startup/capabilities/kill switch, несовместимую
БД, недоступный Redis, отсутствие/ошибку journal replay, независимость ключей,
freshness и вложенные deadlines. Dependency IO подменён; это не настоящий
PG/Redis/provider или пользовательская LIVE приёмка.

До переноса на независимый main base:133 focused PASS, full1768 PASS/16skip,
404 deselected. Эти counts включают несвязанные unit cases из409 и не считаются
exact-final validation новой базы. Итоговый прогон main base фиксируется в
[validation.json](ai-text-runtime-20261108-evidence/validation.json): **1762 PASS/16skip/404deselected**, failures/errors0, новые10 cases входят в1762. Наборы пересекаются, не суммировать.

Ruff новых файлов, mypy нового runtime, input policy и provenance949 PASS.
Frontend TypeScript и production Vite build с mock API disabled PASS.
Frontend tree/package/lock/vite config совпадают до/после переноса на main base.
Build имеет обычное предупреждение о chunk>500kB; browser/LIVE/SLO из него
не следуют. Docker daemon локально недоступен; установка/реестр не менялись.
Windows PostgreSQL18 запущен, но PostGIS extension отсутствует; полноценный
локальный SQL/card/map стенд в этой сессии не запускался.

## Конкретное оставшееся решение

Пользователь не понял первоначальный технический вопрос; это **не разрешение**
на внешнюю передачу текста или расходы. Предложение следует объяснять просто:
модель получает только заранее показанные владельцу фразы об аренде и текущие
typed criteria; объявления остаются в SQL и не отправляются модели.
Для первого закрытого показа выбрать3 фиксированные неперсональные фразы,
например бюджет600€/мес, его уточнение400€/мес и снятие ограничения бюджета,
и согласовать до3 provider attempts с явным дополнительным пределом резерва.
Это предложение, не принятое разрешение и не новый бюджет.

Нельзя переиспользовать неиспользованные старые attempts как автоматическое
разрешение: прежний LIVE UI smoke завершился FAIL, baseline journal52/
575120microUSD исторический, заново не проверялся и не менялся.
Существующий driver и signed admission привязаны к прежнему corpus/случаям;
они не являются готовым launcher для предложенных новых фраз/реальных данных.
Тариф на дату нового запуска и текущие journal counters надо сверить до IO.

После точного решения о provider attempts, cohort и месте закрытого показа —
подготовить разрешённый limited parser, real source mapping/proofs и запуск
существующего UI с новым application composition. Затем проверить реальные
действия пользователя и дать наблюдаемый адрес. Не выдавать текущую подготовку
за показ заказчику. Public real-user outbound/production activation не включены;
S2/S3/S6 partial, voice/saved/delivery/performance/release gates открыты.

# Ttest / 112233.es — итоговый roadmap AI-поиска после аудита парсеров

> **Дата:** 2026-10-25. **Статус:** сводный технический roadmap, НЕ согласованное заказчиком продуктовое ТЗ.  
> **Основной документ:** [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md). **Аудит реализации:** [PARSER_DATA_AUDIT.md](https://github.com/antony502189-max/Ttest/blob/feat/ai-search-parser-audit/docs/ai-voice-search/PARSER_DATA_AUDIT.md).  
> **Разработческий PR:** [#373](https://github.com/antony502189-max/Ttest/pull/373), `feat/ai-search-parser-audit` → `planning/ai-voice-search-architecture`. На дату проверки открыт, **не слит**.  
> Документ размещён отдельно в planning-ветке, чтобы не переписывать изменения файла `IMPLEMENTATION_PLAN.md` в открытом PR.

## 1. Итог аудита: уже сделано / ещё не сделано

### Выполнено в PR #373 (но ещё не в базовой planning-ветке или main)
- Статически проверены все **9** адаптеров источников и цепочка `fetch → parse → normalize → upsert`.
- Исправлен доказанный дефект старого импортного fingerprint: изменения только optional-полей (животные, дети, курение, вместимость и другие canonical scalars) могли оставить canonical listing устаревшим. Написаны регрессионные тесты.
- Реализованы консервативный evidence-extractor по простым полным фразам, состояния `explicit/conditional/conflict/unknown`, отдельное разграничение курения внутри/снаружи.
- Добавлены **26 синтетических золотых кейсов** и read-only CLI `backend/app/commands/audit_ai_listing_data.py`: обработка offline fixtures либо явно заданного `AI_AUDIT_DATABASE_URL`, агрегированные JSON/Markdown отчёты.
- Добавлен чистый `build_listing_evidence_input()`: типизированный очищенный пакет и независимый SHA-256 digest. **Это offline-заготовка, не доказательство полной PII-безопасности**.
- Выполнены заявленные проверки: local non-integration **896 passed / 15 skipped**, GitHub CI на кодовой ревизии `6e8500dc` — **904 passed / 7 skipped** unit и **88 passed** PostgreSQL/PostGIS integration, Ruff и mypy passed. Последние коммиты были документационными; проверять статус PR перед слиянием.

### НЕ выполнено
- Нет реальной проверки реплики/production-выборки объявлений: данные `fixture-data-audit.json` **синтетические, 5 snapshots / 4 active**. Сводный `potential_conflicting_canonical_listings=1` относится только к fixture.
- Нет репрезентативного обезличенного корпуса реальных описаний с ручной разметкой.
- Нет финальной модели provenance, хранения per-source AI-facts, canonical resolver или материализованной таблицы search features.
- Нет durable AI queue/worker, DeepSeek-клиента, model validation, бюджета, платных запросов и массового backfill.
- Нет voice ASR, поискового API, AI-ранжирования, микрофона и утверждённой заказчиком UX/бизнес-логики.
- Не выполнен production privacy/data-processing review; наличие чистого offline-пакета не означает гарантию очистки любых произвольных персональных данных.
- Текущий AI-поиск пока отсутствует. Работающий обычный поиск/TOP должны остаться неизменными до отдельного решения.

### Значимые технические выводы
1. **Вместимость:** для значений **1–10** `room_capacity_v2` уже позволяет сохранить вместимость больше двух; дефект заключался прежде всего в пропуске обновления при неизменном fingerprint. Значения свыше 10 не материализуются в canonical capacity. Семантика обычного `roomCapacity` — **точное равенство**; будущая AI-проверка «поместятся N» должна использовать подтверждённый `capacity >= N`.
2. **Источники:** одна canonical-карточка может агрегировать несколько source records; primary source иногда перезаписывает известный признак на unknown. Политика разрешения конфликтов не реализована.
3. **Legacy defaults:** `False/True/1` сами по себе не являются доказательством утверждения владельца/источника. Не менять исторические строки без отдельного безопасного плана.
4. **Описания и raw:** generic `raw_payload` может включать фрагмент HTML и контакты; в других адаптерах raw — краткий словарь. `normalized_payload` включает вложенный `raw_payload`. **Нельзя отправлять raw/normalized snapshot целиком в LLM**.
5. **География:** наличие coordinates не доказывает точную геопозицию объекта. Фактический `geo_confirmed_pct` сейчас принципиально неизвестен.

## 2. Рекомендованная архитектура (до заказчика — продуктовые правила открыты)

```text
[ВНЕШНИЕ САЙТЫ, только разрешённые detail fetch]
        ↓
existing parsers → source snapshots / canonical listing (PostgreSQL)
        ↓ устойчивый сигнал/периодический reconciler ПОСЛЕ commit
durable job queue  ──[idempotency & hash/version]──▶ AI enrichment worker
        ↓                                            ↓
     monitor                                 sanitized selected evidence
                                                    ↓
                                            external LLM extraction API
                                                    ↓
                                         strict schema + evidence check
                                                    ↓
                                  per-source versioned listing_ai_facts
                                                    ↓
                                   canonical conflict/freshness resolver
                                                    ↓
                                 materialized listing_search_features
                                                    ↓
              [ПОСЛЕ РЕШЕНИЙ ЗАКАЗЧИКА]
voice/text → ASR API (audio only) → intent LLM API → Pydantic
                                          ↓
                         SQL/PostGIS candidate retrieval + scoring
                                          ↓
                           existing listing cards / existing visibility
```

**Принципы:** два независимых контура; LLM вне транзакции импорта; no crawling during a user search; no LLM-generated SQL; no inference of unknown facts; external AI API, не локальные модели; разумный fallback к обычному поиску; без обязательной vector DB для MVP.

## 3. Очерёдность работ — 8 этапов

### Этап 0. Закрыть и принять проверенную parser foundation
**Зависимость:** PR #373; до других code PR желательно получить review.

- [ ] Проверить полный diff PR #373, актуальные зелёные CI на конечной ревизии, migrations/compatibility.
- [ ] Особое внимание изменённому fingerprint: при **первой штатной синхронизации** старые fingerprints обновятся и могут затронуть catalog version и gallery reconciliation. Оценить без массового ручного импортирования.
- [ ] Проверить, что синтетические 26 cases покрывают опасные отрицания, но не заявлять поддержку всех языков/формулировок.
- [ ] Слить PR #373 **только после отдельного решения владельца** в planning branch. Не сливать в `main` и не деплоить автоматически.

**Результат:** принятая в planning-ветку code foundation с регрессиями и защищённым baseline.

### Этап 1. Фактический аудит каталога и описание провалов (read-only)
**Зависимость:** инструмент PR #373. Это **ближайший практический шаг**.

- [ ] На разрешённой staging/read-only replica использовать `AI_AUDIT_DATABASE_URL` с настоящей read-only ролью: `python -m app.commands.audit_ai_listing_data --database --output audit.json`. Не подключать личный production DSN; не делать массового crawling.
- [ ] Вывести по каждому реально активному источнику: `n`, долю и длины описаний, title, explicit/conditional/unknown/conflict по pets/children/smoking/couples/capacity, геопозицию (наличие отдельно от verified precision), provenance gaps.
- [ ] Перепроверить потребление памяти инструмента при реальном размере: текущая агрегация хранит списки длин и canonical conflict groups.
- [ ] Без персональных данных и исходного HTML выбрать по возможности **50–100** реальных объявлений **на источник**, если источник содержит столько записей; иначе весь доступный небольшой набор. Проверить, теряется ли описание по цепочке parse/normalize/upsert и есть ли явные structured policy fields.
- [ ] Зафиксировать включённость источников, фактическую полноту и приоритет исправления адаптеров **по результатам**, а не по 4 synthetic entries.
- [ ] Сформировать обезличенный gold-set реальных policy-фраз: labels, evidence, unknown/conditional/conflict. Синтетический набор сохранить как отдельный слой тестов.
- [ ] Сделать `BACKFILL-001` dry-run: количество eligible записей, распределение длины текстов, оценка token/cost без платных API.

**DoD:** достоверная source coverage matrix, no secrets/raw text в агрегатных артефактах, source-specific defect list, dataset provenance, baseline количества/стоимости. Если нет разрешённой replica — закрыть код/fixtures, а фактический замер оставить явно открытым.

### Этап 2. ADR на семантику совместимости и provenance
**Зависимость:** код foundation + предварительные выводы этапа 1; можно вести параллельно с replica audit.

- [ ] **ADR-1 provenance:** source record, specific provider field или точная quote-evidence, статус `explicit_true/explicit_false/conditional/unknown/conflict`, observation timestamp, extractor/prompt version и quality/staleness.
- [ ] **ADR-2 owner precedence:** явное утверждение владельца сохраняется как отдельная категория; owner defaults не выдавать за выбор владельца; manual override оформлять отдельно и аудировать.
- [ ] **ADR-3 conflicts:** только активные и свежие источники участвуют в текущем резолвинге; если два равно достоверных утверждения расходятся — `conflict`, не автоматически `true`. При удалении/закрытии source исключать из текущей проекции, сохраняя историю.
- [ ] **ADR-4 occupancy:** `confirmed_capacity` — отдельный факт от `current_residents` и `couples_allowed`; допустимая вместимость/пары/дети — разные оси. Не изменять обычный exact filter; AI matcher в будущем использует `>= party_size`.
- [ ] **ADR-5 scope:** правила животных по виду/размеру/количеству; курение indoor/outdoor; дети/студенты/пары/друзья; сезонность, период цены и неизвестные признаки.
- [ ] **ADR-6 privacy:** source-evidence minimization, режим хранения исходного текста, удаление, права субъектов, data retention и договоры с AI-провайдером.
- [ ] Описать конечный Pydantic факт-контракт; запретить факт `explicit` без подтверждённого источника. Confidence модели не равно доказательству.

**DoD:** согласованные ADR, state machine и конфликтные тест-кейсы, чётко описанные решения, не зависящие от ещё не полученных ответов заказчика. Product ranking/TOP оставить отдельным ADR позже.

### Этап 3. Expand-only база для AI-фактов
**Зависимость:** ADR этапа 2.

- [ ] Alembic миграция для versioned per-source facts (`listing_ai_facts`) с `source_record_id`, hash, schema/extractor/provider version, structured facts + evidence, timestamps/status; idempotent unique keys.
- [ ] `listing_search_features`: по одному canonical-агрегату на listing, indexed typed facts или документированная JSONB/index стратегия, provenance/conflicts/freshness.
- [ ] Durable queue/outbox в PostgreSQL (или эквивалент с crash recovery), task identity `source_record_id + input_hash + schema/extractor_version`. Периодический reconciler лечит потерянные события.
- [ ] Реализовать `canonical resolver`; тестировать changed primary, duplicate, retirement, removal, owner choice, unknown vs explicit, stale source и reactivation.
- [ ] Не модифицировать legacy `listings` и действующие DTO в миграции; раздельный feature flag на потребление новых search features.

**DoD:** expand-only/rollback-safe миграции на disposable PostGIS, snapshot/duplicate/resolver тесты, fast filtered query plan, старые страницы продолжают работать.

### Этап 4. Source fidelity и privacy gate
**Зависимость:** реальные проблемы из этапа 1 и факт-контракт этапа 2.

- [ ] Улучшать **только те адаптеры**, где реальные примеры доказали потерю описания или конкретных structured provider fields. Сохранять правила URL, цену, географию, фото, source identity и availability.
- [ ] Проверить route-ID matching для meta/JSON-LD/embedded кандидатов; «описание соседнего объявления» недопустимо.
- [ ] Расширить allowlisted provider facts с evidence path; не передавать whole raw HTML/JSON в LLM. Не угадывать сведения из изображений или отсутствия текста.
- [ ] Усилить `build_listing_evidence_input()` проверенным outbound privacy gate; тесты на контакты, скрытые/обфусцированные данные, возможный page chrome и prompt injection.
- [ ] Empty/very short source → `insufficient_source_data` и допустимый selective **background** refetch, а не гадание LLM.
- [ ] Жизненный цикл обычного импортёра и dedup/галереи не менять без новых регрессий.

**DoD:** измеримый прирост реальных `description/verified fact coverage`, отсутствие опасных regression failures, проверенные обезличенные LLM inputs.

### Этап 5. Пилот LLM-обогащения и отдельный worker
**Зависимость:** этапы 2–4; сетевые провайдеры только после privacy approval.

- [ ] Provider-independent `ListingFactExtractor`: одна задача — одно source evidence input; **никаких SQL/tools/browser** у LLM.
- [ ] Сначала offline A/B на размеченном корпусе: regex baseline и несколько моделей/промптов; оценить false explicit permits, пропущенные запреты, ошибки conditional, supported evidence, p50/p95/cost.
- [ ] Structured JSON/Pydantic + проверка evidence и типов; unsupported/ambiguous → unknown/review, не «разрешено».
- [ ] Реализовать независимый worker: retries с backoff/jitter, 429/timeouts, dead-letter, caps и breaker, status metrics, bounded concurrency, ключи через server-side secrets.
- [ ] После LLM вернуться к БД и проверить актуальность `input_hash/schema_version/source_status`; устаревший ответ не записывать как текущий.
- [ ] При сбое LLM импорт продолжает работать; задание остаётся ожидающим, старые валидные факты не стираются.
- [ ] Стейджинговый интеграционный прогон на небольшой контролируемой партии и сверка с ручной разметкой.

**DoD:** стабильный async ingestion, доказуемое отсутствие false-positive разрешений сверх утверждённого quality gate, измеренная стоимость, логи без PII, безопасный disable/retry.

### Этап 6. Backfill и реальная готовность каталога
**Зависимость:** успешный контролируемый пилот.

- [ ] Dry-run: очередь источников, текущее состояние, cost cap, количество задач по source, доля `insufficient_source_data`.
- [ ] Запустить на staging **небольшими идемпотентными партиями**, отслеживая backlog/показатели/расходы.
- [ ] Отдельно ревизовать unknown/conflict/conditional, не подменяя их позитивным результатом.
- [ ] Материализовать canonical features только для актуальных публичных listings; inactive/missing/closed источники не дают текущих фактов.
- [ ] Повторный прогон того же input hash не должен повторять оплачиваемый extraction. Новые версии данных/схемы запускают новую задачу.
- [ ] После разрешения владельца — постепенная выкладка по источникам в production с флагами и откатом, без массовых чисток и несанкционированного crawling.

**DoD:** измеренный source coverage, conflict rate, цена на 1000 объявлений, время восстановления, свежесть признаков и сохранность действующего каталога.

### Этап 7. Пользовательский AI/voice поиск — только после ответов заказчика
**Зависимость:** готовые search features и утверждение продуктовых сценариев.

- [ ] Согласовать 38 вопросов: обязательность профиля, hard/soft constraints, unknown alternatives, язык/UX микрофона/текста, сохранение сессии, карта, TOP и уведомления.
- [ ] A/B тестировать ASR на добровольных RU/ES/EN и смешанных топонимах, числах, отрицаниях, суммах евро. Выбирать по **critical slot error rate** + задержкам и стоимости, а не названию модели.
- [ ] Отдельный `IntentExtractor`: transcription/text → типизированные фильтры, различает «у меня собака» и «собаки разрешены», «не курю» и «хочу жильё, где никто не курит».
- [ ] Продумать server-side сессию/состояние уточнения без предположения, что LLM хранит историю.
- [ ] FastAPI endpoints и request schemas обсуждать после UX; провайдерские ключи не передавать клиенту; лимиты аудио, permissions policy, scoped nginx body limit, анонимные quotas.
- [ ] PostgreSQL/PostGIS candidate retrieval → deterministic hard checks/soft scoring по prepared features; unknown/conditional/conflict выводить честно, опасные несовместимости исключать из confirmed matches.
- [ ] Не допустить утечки неактивных/закрытых listings. Коммерческую логику TOP изменить только после отдельного утверждения. Сохранять доступ к обычному поиску при AI-отказе.

**DoD:** e2e voice/text пользовательский сценарий с контрольным набором, понятные предупреждения, работоспособность карты/карточек/фильтров, производительность, безопасность и согласованная продуктовая логика.

## 4. Последовательность PR — без выдумывания номеров

| Очередь | Название | Зависимости / цель |
|---|---|---|
| PR #373 (открыт) | Parser data foundation | Review → merge только в planning branch по отдельному разрешению |
| PR-1 | Read-only real catalog coverage & anonymized gold set | После принятия #373; реальные измерения |
| ADR-PR | Provenance, conflict, occupancy, privacy | В параллель PR-1, финал перед DB-schema |
| PR-2 | Expand-only AI facts / canonical feature schema | После ADR |
| PR-3 | Targeted per-source fidelity and outbound privacy | После PR-1, ADR |
| PR-4 | Durable queue, reconciler, resolver | После PR-2 |
| PR-5 | LLM provider adapter, validation and async worker | После PR-3/4 + privacy gate |
| PR-6 | Staging backfill, QA, opt-in rollout | После контролируемого пилота |
| PR-7+ | Voice/intent API, matching, UX | После ответов заказчика и catalog-readiness |

Каждый PR: отдельная ветка, tests, code review, changelog. **Ни один не означает автоматический merge в main или production deploy.**

## 5. Приоритетные риски / стоп-факторы

| Риск | Почему важен | Gate |
|---|---|---|
| Ложное `pets_allowed=true` | Обман пользователя / неподходящее жильё | Размеченные реальные отрицания + precision и manual review |
| Owner/provider defaults | Можно ошибочно «запретить» жильё | Provenance / no default as confirmed |
| Primary source overwrites | При дубликатах известное сменяется unknown | Source facts + resolver |
| Пустой/слабый текст | LLM не извлечёт то, чего нет в данных | Per-source measured coverage / selective parser fixes |
| PII и raw HTML | Провайдеру уйдут контакты/персональные сведения | Outbound privacy review + allowlist |
| Freshness / stale jobs | Неактуальные запреты и карточки | Content hash, source status, reconciler |
| Цена AI API / retry storms | Неконтролируемые расходы | Quotas, tokens/cost dashboard, bounded retries |
| Модель ASR путает числа/не | Неверная стоимость или жесткое условие | Critical slot error benchmarks |
| Голосовой UX/TOP не утверждены | Неверная продуктовая логика | Заказчик и отдельный product ADR |

## 6. Измеримые acceptance criteria, которые надо утвердить

**Не выдавать эти целевые значения за результаты уже выполненного аудита.** Предлагаемые ориентиры для pilot-gate:
- Zero undocumented destructive modifications; unit/integration regression CI зелёный.
- Контрольная выборка *не меньше ~100–200 обезличенных реальных кейсов в сумме* и покрытие каждой фактически активной source-категории с доступными примерами; статистическую значимость оценивать по числу кейсов каждого типа.
- Для safety-critical «разрешено», особенно pets/couples/children, **нулевая доля известных ложных разрешений на контрольном наборе** как начальный gate; затем задать CI/precision bound на достаточной выборке. Это цель пилота, не доказательство нулевого риска в мире.
- Непроверенные факты никогда не отображаются как подтверждённые; unsupported/unknown remains unknown.
- Failed/outdated tasks не мешают импорту и не перезаписывают свежие факты.
- Cost per 1000 analyzed listings, p50/p95 background time, % facts explicit/conditional/unknown/conflict измерены до backfill; значения бюджетных порогов утвердить отдельно.
- QA проводит полноценную проверку исходного поиска, цены (включая лимит long €1000), availability, TOP, gallery, dedup и географии.

## 7. Следующее конкретное действие

**Не заказывать второй большой промпт «сразу сделать DeepSeek».** Сначала:
1. Review PR #373, перепроверить окончательную ревизию и решить о merge в planning branch.
2. С помощью уже написанного CLI выполнить **авторизованный read-only аудит реального каталога** на реплике/TEST. Если инфраструктуры пока нет — документировать блокер, не использовать prod-write DSN.
3. Параллельно утвердить **ADR provenance + conflicts + occupancy**, затем запускать PR-2 для DB schema.

**После этих трёх действий** станет понятно, сколько реальных объявлений можно обогатить без повторного fetch, где нужно чинить парсеры, сколько будет стоить LLM, и как корректно строить поиск.

## 8. Материалы, на которых основан roadmap

- Загруженный `IMPLEMENTATION_PLAN.md`, включая Section 12 PR #373 status;
- Загруженный `PARSER_DATA_AUDIT.md` с source matrix, reproductions, CI и limitations;
- Загруженный `fixture-data-audit.json` — *synthetic offline* sample, не реальная статистика каталога;
- [PR #373 в GitHub](https://github.com/antony502189-max/Ttest/pull/373) — открыт и не слит на момент составления.

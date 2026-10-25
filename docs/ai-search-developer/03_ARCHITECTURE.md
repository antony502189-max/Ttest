# 03 — Архитектура AI-поиска: две независимые цепочки

## Концепция

Вместо браузерного агента, который открывает чужие сайты при пользовательском запросе, используем уже существующий импортёр и локальную базу. LLM извлекает **строго проверенные факты** из текстов вне пользовательского пути, а пользовательский LLM превращает запрос в **validated intent**. SQL/PostGIS ищет по подготовленным данным. Ни одна LLM не выбирает SQL, лицензии, стоимость или доступность самостоятельно.

## Обязательное ограничение времени ответа

**Голос: p95 ≤10 секунд от отправки завершённой записи до появления подходящих карточек в браузере** при нормальных условиях. UX — один Send → автоматически ASR + intent + indexed DB search → существующие карточки, **без обязательного второго клика для подтверждения транскрипта**. Распознанный текст доступен для добровольного исправления после/параллельно отображению. Контур A обязан оставаться асинхронным и не участвовать в runtime поиске. Не добавлять Places/Routes/live scraping/перепроверку каждого объявления при запросе. Полные end-to-end budgets и freshness rules: [09_PERFORMANCE_SLO.md](09_PERFORMANCE_SLO.md).

## Поток A — фоновое обогащение (не blocking import)

```text
existing allowed parser → source snapshot/canonical upsert → DB COMMIT
      ↓ durable marker/reconciler (not network request in SQL transaction)
PostgreSQL AI jobs: source_id + content_hash + schema/extractor version
      ↓ independent bounded worker
selected cleaned title/description/provider evidence (no raw HTML/contacts)
      ↓ DeepSeek Flash (extractor schema; no tools/browser)
Pydantic validation + evidence span/source key verification
      ↓ per-source versioned facts (status, evidence, origin, fresh_at)
canonical resolver (active sources, owner explicit priority, conflicts, stale)
      ↓ materialized listing_search_features (indexed)
```

Инварианты:
- Сбой DeepSeek не блокирует импорт, публикацию, фото, source health.
- Stored legacy `False/True/1` сам по себе **не доказательство** owner/provider permission.
- Source disagreement -> `conflict`; no evidence -> `unknown`; scoped pets/smoking -> `conditional`.
- Перед активацией результата worker повторно проверяет current content_hash и source_status; old/late job не перезаписывает новый fact.
- Фоновый worker не выполняет повторный full crawl при поиске пользователя.
- AI queue имеет durability, retries/dead-letter/lease/recovery, изоляцию от импортёра и email worker.
- Owner-written explicit answer сохраняет происхождение; LLM не заменяет волю собственника.

## Поток B — интерактивный поиск

```text
React text or completed audio recording
     ↓ FastAPI daily quota check/reservation + technical anti-abuse
audio? -> Groq Whisper Large V3 completed-file transcription -> editable text
     ↓ DeepSeek Flash intent extraction (strict JSON)
structured intent patch + session state (authenticated/anonymous TTL)
     ↓ Pydantic validation (hard/soft/location/price/party/pets...)
PostgreSQL SQL/PostGIS candidate filtering + stored listing_search_features
     ↓ verified compatibility + existing TOP/boost sorting + pagination
existing ListingCardResponse + deterministic reason codes/text
     ↓ existing React PropertyCard / MobileResultCard and existing map
success -> finalize quota debit exactly once; errors -> release reservation
```

## Иерархия слоёв

1. **Identity/quota/authorization**: сервер, не frontend/LLM; 3 guest / 200 logged, daily Madrid.
2. **ASR**: Groq primary, OpenAI GPT-Transcribe fallback. После записи, без TTS/live streaming.
3. **Intent**: DeepSeek Flash, no SQL/tools; model output validates strict Pydantic.
4. **Session**: только normalized filters+patch, TTL; не нужна новая vector DB для MVP.
5. **Search**: существующие Listing search handlers, visibility, price, rental category, geography; separate confirmed capacity >= N; query BEFORE pagination.
6. **Ranking**: **hard eligibility** исключает запрещённые варианты, далее коммерческие TOP keys unchanged, затем релевантность только где не ломает платные позиции.
7. **Presentation**: existing cards/galleries/labels/links/map; explain matching from verified reason codes; no new cards.

## Модель условий

Факт на уровне source:
- `status`: explicit_allow / explicit_deny / conditional / unknown / conflict / legacy_unverified;
- typed `value` + `qualifiers` (species/size/count/indoor/outdoor/etc.);
- `evidence` (короткий допустимый фрагмент) + `origin` (description, title, exact provider field, owner explicit);
- `source_record_id`, `listing_id`, `input_hash`, `extractor/schema_version`, `observed_at`;
- ограниченный набор справочников и разрешённых значений.

Отдельно: `confirmed_capacity` не является ни `roomCapacity` для текущего интерфейса, ни количеством жильцов сейчас, ни разрешением для пары. Match «для N» => >= N только если вместимость доказана.

## Важнейший архитектурный долг

Три источника могут утверждать «разрешены животные», «запрещены» и «ничего не сказано». Текущий primary snapshot может затирать значение. Новый resolver должен оставлять конфликт, а не превращать последний import в истину.

## Неизменяемое

Стандартный поиск, существующая карта и внешние карточки, долгосрочная аренда ≤€1000, holiday mode, галереи/ссылки, auth, favorites, Stripe и TOP promotions, protections against mass removal. Никаких новых jobs/POI/routes/flow карты. Разработка только по flags и маленьким совместимым PR.

См. подробный [AI Integration Readiness](audits/2026-10-25/AI_INTEGRATION_READINESS.md).

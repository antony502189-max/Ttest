# 04 — Предлагаемые API и контракты (НЕ реализовано)

> **DRAFT**: пути/DTO нужно сверить с реальным FastAPI router, Pydantic схемами, нынешним body limit и форматом ошибок Ttest. Не объявлять ниже backend-реализацией. Подключение оплачиваемых API только после provider/privacy approval.

## Основные эндпоинты

| Метод | Предлагаемый путь | Доступ | Задача |
|---|---|---|---|
| GET | `/api/v1/ai-search/quota` | гости и пользователи | limit/used/remaining/resets_at/пользовательский status |
| POST | `/api/v1/ai-search/transcriptions` (внутренний/опциональный) | гости и пользователи | completed audio → transcript; **клиент автоматически вызывает query без подтверждения пользователя**, оба этапа входят в 10 секунд |
| POST | `/api/v1/ai-search/query` | гости и пользователи | текст либо **один multipart completed-audio запрос** → ASR→intent→DB→карточки, ≤10s p95 browser end-to-end; quota finalize один раз |
| POST | `/api/v1/ai-search/sessions` (опционально) | гости и пользователи | создать/очистить короткий session state |
| существующие | SavedSearch + Notifications endpoints | **после входа** | сохранить structured search; alerts через существующий outbox |

### Обязательный быстрый голосовой путь (НЕ добавлять confirmation gate)

Пользователь **один раз отправляет** запись → backend сам вызывает Groq batch ASR и DeepSeek intent → возвращает актуальную выдачу **не дожидаясь подтверждения транскрипта**. Текст можно исправить добровольно после выдачи; это новый последующий запрос, если пользователь его отправит. Предпочтительно один multipart `/query` со всем pipeline. Если остаются `/transcriptions` + `/query`, frontend вызывает их автоматически, и **суммарное** время до отрисовки входит в общий **p95 ≤10s**, не более одного бизнес-дебета. Считать скелетон, transcript и HTTP 200 результатом **нельзя**. Учитывать source freshness/visibility и не запускать re-import/crawling на каждый user request. Контракт в [09_PERFORMANCE_SLO.md](09_PERFORMANCE_SLO.md).

### Дневной quota contract

```json
{
  "dailyLimit": 3,
  "used": 1,
  "remaining": 2,
  "resetsAt": "2026-10-26T00:00:00+01:00",
  "authenticated": false
}
```

Пример illustrative: конкретный offset зависит от DST. Authenticated dailyLimit=200, anonymous=3. Inconsistent login transition, parallel requests, double submit и 429 нужно покрыть integration tests.

**Рекомендуемая реализация**: PostgreSQL authoritative `ai_usage_days` + `ai_search_requests`, атомарные reserve/finalize/release и idempotency key. Redis — existing infrastructure для TTL-сессий и антиабуза, **не единственная история бизнес-квот**. Не списывать на ошибке провайдера. Отдельно технически ограничить бесплатные повторения `transcriptions`, чтобы не создавать неограниченный счёт у Groq.

### Search intent (пример)

```json
{
  "schemaVersion": 1,
  "inputText": "Мы с девушкой и маленькой собакой ищем комнату до 650 евро в Адехе",
  "sessionId": "opaque-session-id",
  "intent": {
    "rentalMode": "long_term",
    "propertyTypes": ["room"],
    "adults": 2,
    "relationship": "couple",
    "children": null,
    "pets": [{"species": "dog", "size": "small"}],
    "location": {"municipality": "Adeje"},
    "budget": {"preferred": 600, "hardMax": 650, "currency": "EUR"},
    "hard": ["rentalMode","propertyTypes","adults","pets","location","budget.hardMax"],
    "soft": []
  }
}
```

Детали JSON — **не** контракт, пока не подписан ADR. Идентичный объект нужен и текстовому и голосовому потоку. Не спрашивать животных/детей/курение без необходимости.

Follow-up «теперь с балконом» = patch `amenities.balcony=required`, **не** заменить все фильтры. Удаление `unset` должно быть явным. При смене intent invalidates old cursor.

### Search response (пример)

```json
{
  "schemaVersion": 1,
  "text": "Нашёл варианты по вашему запросу.",
  "results": {
    "items": ["existing ListingCardResponse objects"],
    "total": 10,
    "nextCursor": null
  },
  "explanations": {
    "listing-id": {"reasons": ["capacity_confirmed", "pets_small_dog_allowed"], "needsConfirmation": []}
  },
  "quota": {"dailyLimit": 200, "used": 2, "remaining": 198},
  "sessionId": "opaque-session-id"
}
```

Здесь массив items — placeholder, не настоящий serialized card. Реально **переиспользовать существующий bounded card DTO**, включая gallery и source redirect. TOP/server sort неизменён. Reason codes строятся детерминированно из evidence, **не LLM-сочинение**.

## Безопасность media upload

- Browser `getUserMedia/MediaRecorder` только после клика; permission same-origin; остановка tracks после завершения/отмены.
- В main на snapshot: `microphone=()`, поэтому необходимо review headers в `deploy/nginx.conf` и `backend/app/main.py`; не использовать wildcard `*`.
- Выделенный multipart route и scoped лимиты. Стартовое proposal: ~60 секунд / 8 MiB аудио; тестировать контейнер/codec/length, Safari mp4 vs webm, 25 MB внешнего API.
- Нельзя расширять глобальный JSON body лимит 256 KiB ради аудио.
- Файлы transient, не сохраняются в базе; temp private, cleanup on error.
- Никаких remote URLs для загрузки аудио (SSRF). Server-side provider secrets, no frontend embedding.

## Коды отказов

`quota_exhausted`, `transcription_invalid`, `transcription_failed`, `intent_invalid`, `provider_unavailable`, `search_no_confirmed_matches`, `request_in_progress`. Проверить envelope/error mapping по текущему API. Избегать потери quota на 429/5xx, повторных idempotent submissions и отменённых запросах.

## Provider abstraction

- `SpeechTranscriber`: Groq Whisper Large V3; OpenAI GPT-Transcribe запасной; фичефлаг/timeout/retries.
- `SearchIntentExtractor`: DeepSeek Flash, strict validation; prompt/version metrics.
- `ListingFactExtractor`: separate prompt/schema/worker; privacy evidence gate до отправки.
- Сравнение качества на реальных обезличенных ру/испан/англ/смешанных фразах с числами, отрицаниями и топонимами. Не делать оплаченные calls в docs PR.

Подробнее: [readiness ``9–12](audits/2026-10-25/AI_INTEGRATION_READINESS.md).

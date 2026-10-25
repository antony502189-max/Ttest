# 08 — Задачи разработчика и handoff status

## Статус на подготовку папки: 25.10.2026

- [x] Получен read-only audit Codex (3 отчёта, реальный серверный snapshot, источники/пробелы; **без real DB read-only inventory**).
- [x] Владелец утвердил: нет вакансий/новых карт/маршрутов/TTS/live ASR; карточки и TOP не трогать; 3/200, Madrid midnight, auth-only saves, no monthly spend cap.
- [x] Выбран предварительный провайдерный стек: Groq Whisper Large V3 batch + DeepSeek Flash, резерв OpenAI GPT-Transcribe; реальные provider accounts не проверены.
- [x] Владелец добавил **целевой p95 ≤10 секунд от отправки законченной голосовой записи до появления реальных актуальных карточек**, без обязательной второй кнопки. Документация: [09_PERFORMANCE_SLO.md](09_PERFORMANCE_SLO.md). **Результат пока не измерен/не реализован**.
- [ ] Review #373 (не слит на дату snapshot), проверить актуальность main и payment #372.
- [ ] PR-AI-01 ADR facts/intent/commercial sort + code examples, без deployments/API.
- [ ] Авторизовать readonly DB replica/роль и выполнить source coverage audit (не с production write DSN).
- [ ] Исправить существующие 422 address fixtures/fullstack CI и определить branch protection отдельной задачей.
- [ ] Дальнейшие кодовые PR см. [05_IMPLEMENTATION_PLAN](05_IMPLEMENTATION_PLAN.md).

## Критические ворота перед реальной интеграцией

| Вопрос | Status | Требуется |
|---|---|---|
| Реальная полнота описаний/условий | **UNKNOWN** | readonly DB coverage, n/duration/type/source per-criterion |
| Политика source conflicts/provenance | **NOT APPROVED** | ADR + tests, source-level evidence |
| Нормативное DPA/ASR retention | **UNKNOWN** | provider/legal review до передачи данных |
| Готовность Groq/DeepSeek ключей | **NOT CONFIGURED на snapshot** | secure provision через ops по разрешению |
| Платный pilot | **NOT AUTHORIZED** | отдельное решение владельца, без месячного spending cap |
| Quota 3/200 | **NOT IMPLEMENTED** | PG authoritative ledger + Redis antiabuse |
| React mic | **NOT IMPLEMENTED** | same origin microphone header + scoped audio endpoint |
| AI enrichment | **NOT IMPLEMENTED** | facts DB + queue/worker/resolver |
| Main protection / flaky suite | **NEEDS CHECK** | current CI+ruleset recheck |
| Tourist legal questions | **OPEN** | проверка действующих требований, без неподтверждённых новых правил |

## Для следующего агента/разработчика

1. **Сначала** прочитать README → Product → Production → Architecture → API → PR plan.
2. Не начинать с «установить demo ZIP на VPS» — его код не проверен и он не нужен для нативного модуля.
3. Не пытаться решить неверную релевантность сменой Groq/DeepSeek, пока не измерена достоверность listing data.
4. Не объявлять provider specs/prices неизменными: запросить текущие официальные docs перед live integration.
5. Каждый PR: задача/ветка, код/миграции, тесты, CI URL+SHA, evidence, какие риски остались, update this file.
6. Никогда не писать «выполнено в production», если проверен только код или CI.

## Рекомендуемое первое задание Codex

> Сверь актуальные `main`, `planning/ai-voice-search-architecture` и PR #373, прочитай `docs/ai-search-developer/`. Создай отдельный **документационный** PR-AI-01 с ADR provenance/conflict, confirmed_capacity semantics, source freshness, preserved TOP/boost rules, versioned ListingFact/SearchIntent/Patch DTO examples, quota 3/200 Madrid midnight, 12+ негативных кейсов и правилами отказоустойчивости. Не создавай миграции, clients, endpoints, не трогай prod, не вызывай оплачиваемые API и не сливай PR самостоятельно. После выполнения предоставь SHA/PR link и матрицу covered requirements/tests.

Обновить журнал после выполнения любого шага (не подменять checkbox ссылкой на план).

# AI Search на 112233.es — единый план завершения

Версия **3.3**, 4 ноября 2026. Этот файл определяет порядок оставшихся работ и хранит прогресс. Технические документы и отчёты ниже служат основаниями, а не конкурирующими планами.

## Цель, текущий этап и следующий шаг

**Конечный результат:** посетитель 112233.es вводит текст или отправляет голос, получает реальные подходящие объявления и уточняет условия; после регистрации сохраняет AI-поиск и получает уведомления о новых совпадениях. Функция работает на сайте с настоящими backend, моделью и обновляемым каталогом. Обработаны ошибки, квоты и восстановление. Текстовый стенд — промежуточный результат, а не завершение всей функции.

**Текущий этап: S2 — рабочий каталог и обновление фактов. S1.1–S1.3 выполнены в пределах подготовки и targeted merged-source проверок; продуктовые A1–A12 остаются открытыми.**

**Следующее действие S2.2:** exact-head Linux CI исправлений внешнего review#407 на source `d797e68ad0ec9d6dba690a3b063fa080f87b5b65`, затем повторная оценка владельцем. F-01/F-02/F-03/F-04/F-05 и T-01–T-03 обработаны; F-01 использует прямо разрешённый review вариант trusted dynamic mock без ложной callback attestation. Новые local checks:1752unit PASS/16skip,402facts PG PASS/1skip,54verified cards/map/gallery PASS; Ruff/mypy175, migrations/check и947inputs provenance PASS. [Review/evidence](reports/PR407_REVIEW_FIXES.md). Старый b256f95f CI11SUCCESS отдельно от нового source; PR draft, ready/merge/deploy не выполнялись. S2 partial, S3–S7/B2–B6 OPEN.**

**Историческая передача до merge#406 (04.11):** пользователь запросил GPT‑6.1 Sol (`gpt-6.1-sol`), reasoning `medium`, полный доступ и автономное продолжение S2.2. Model/thinking задаются через create_thread; permissions нужно подтвердить по developer runtime context нового чата, а не по тексту prompt. Не просить повторных общих разрешений на уже согласованную local synthetic/disposable работу. После проверки фактического профиля сразу реализовывать process lifecycle rehearsal, без нового общего аудита или roadmap. Исторические post-merge #404 main ece1632e evidence остаются историческими; база на момент этой передачи —20435c2e. Актуальная merged база для#407 —1990638d61ada0960a864e34568db306151f442b.

**Исторический срез S2.2 до полного review:** создан [draft PR#406](https://github.com/antony502189-max/Ttest/pull/406), merge/deploy не выполнены. Python source/tests — `c4b32cb4`; последующий runtime-boundary commit `2c3c6ffa05425c9fc8a95dab8ffe9f98eb6f9cf1` добавляет только scoped `.gitattributes` для сохранения evidence bytes и обновлённый manifest, application/lab/test Python не менялся. Hashes проверены и для committed Git blobs; owned PostgreSQL container/anonymous volume удалены. CI первого PR head запущен, final exact-head Linux результат пока не подтверждён; не переносить88local PASS на CI. S0–S1 прежние границы, S2 partial, S3–S7/B2–B6 OPEN.

**Review04.11, локальный срез до финального CI:** по прямому запросу владельца выполнено полное self-review diff#406, шесть подтверждённых findings имеют RED→GREEN. Исправлены false committed на clean exit, startup deadline accounting, двойной reap budget, arbitrary parent pickle, parent error redaction и fixture schema binding. Owned review PG/volume удалены. Код проверен локально, exact-head CI нового source ещё ожидается; merge/deploy не выполнены. S0–S1 прежние границы, S2 partial, S3–S7/B2–B6 OPEN.

**Итог CI/review04.11:** head1fe59146 —11/11workflows,18/18jobs SUCCESS. [Combined facts/PostGIS/HTTP/browser](https://github.com/antony502189-max/Ttest/actions/runs/41806676886), [production audit](https://github.com/antony502189-max/Ttest/actions/runs/41806676510), [mobile](https://github.com/antony502189-max/Ttest/actions/runs/41806676622). PR#406 переведён в ready, open/merged=false; новых незакрытых findings в проверенном diff нет. Snapshot output/pr406-final-ci-1fe59146.json, SHA256=83339ff7661464af8249b18da2713ce7defa7c757fb59efa6b627ef943f3c7b6. Описание PR содержит exact-head CI proof; этот финальный статус плана сохранён локально и синхронизирован в canonical root без изменения проверенного PR head. Следующее действие указано выше; merge/deploy не выполнялись.

**Merge#406 / S2.2 detail04.11:** GitHub merged=true,04.11 в12:46:54Europe/Moscow, merge/main1990638d; fetch подтвердил тот же origin/main. Existing worktree сохранён, новая codex/ai-search-detail-refresh от merged main; локальные review statuses перенесены, старый root с чужими изменениями не менялся. Post-merge main на13:23:36:5/6SUCCESS, Full audit in_progress. Новый code source716ae9fa — отдельные local tests/CI, не deployed release. Synthetic detail contract продвинут, standing supervision и real data gates не закрыты.

**Review#40704.11:** по прямому запросу владельца обработан внешний PR407_CODEX_REVIEW_REPORT.md. PostgreSQL RED9fail/2pass подтвердил type-metadata/header проблемы и динамическую mock-модель; после fixes новые local checks PASS. T-01 проверяет actual new consumer→verified SQL count/cards/map до LIMIT при403/429/timeout/invalid detail и сохранение manual4; T-02 — public multi-source partial commit/reopen/replay при HTTP/invalid/DB fault. Новая инфраструктура вне findings не добавлялась. Исторические validation/raw snapshots не переписаны; после старого local pre-CI среза b256f95f имел11SUCCESS workflows, новый exact-head CI ожидается. Owned PG/volume удалены после всех suites; реальная БД/provider/budget не затронуты.

## Установленное исходное состояние

04.11, повторная проверка S2.2 по вопросу владельца «что теперь»: PR#406 open/draft, merged=false, head `17d2857f03ef1b303d46918f6d1d2cc9632e160f`. На точном head11workflows:3SUCCESS (snapshot/security/capacity),2in_progress (combined facts/mobile),6pending; failure пока нет, итоговый CI не подтверждён. [Combined facts run](https://github.com/antony502189-max/Ttest/actions/runs/41803809833). Следующее действие остаётся одним: exact-head CI/review#406; после него продолжать S2 source-specific refresh chain. Код и другие S0–S7 статусы не менялись.

Пользователь подтвердил: AI Search — новая функция сайта 112233.es, репозиторий `antony502189-max/Ttest`.

03.11.2026 через GitHub проверен **main `4a60e1632d3b234f4b5321d224b3abfd041769a3`**, merge PR #403. Сохранённый `origin/main` указывает на тот же SHA. Рабочая папка `C:\Users\HONOR\Documents\Codex\Ttest` находится на старом локальном main `f7845b16f0d31f4d03ded2e2cedebf17bad1a2f4` и содержит чужие незавершённые изменения. Поэтому отсутствие AI в этой папке объяснялось устаревшим checkout. Прежний вывод о неопределённом проекте исправлен.

Код изучен через `git show origin/main:…`, без reset, переключения ветки или изменения существующих worktrees. На исходном S0 production-версия, текущие контейнеры и CI не проверялись; новые post-merge S1.3 результаты приведены ниже. Результаты ниже взяты из сохранённых отчётов; это не новые прогоны на merged main.

| Область | Уже реализовано | Осталось |
| --- | --- | --- |
| Текстовый UI | `src/components/home-ai-search.tsx`, `ai-conditions.tsx`, `ai-result-map.tsx`, `src/api/ai-search.ts`, `ai-continuation.ts`; восстановление после reload улучшено в #403 | Приёмка произвольных запросов через настоящую разрешённую модель в целевой среде |
| Backend | `backend/app/api/v1/ai_search.py`: AISearchRuntime; `services/ai_search_execution.py`: TextSearchExecution; sessions, ownership, ledger, exact replay | Обычный app.main регистрирует routes, но не создаёт runtime; нужна рабочая сборка зависимостей |
| Факты и поиск | FactPipeline, bridge/worker, typed hard matching, query proofs, verified cards/map, current-input/freshness guards | Постоянное обновление, измеренное покрытие рабочего каталога и supervised pipeline |
| Закрытый стенд | `backend/lab/ai_text.py`, `lab/decision_parser.py`, `deploy/ai-text-lab`, `scripts/ai-text-lab.ps1`; сохранены functional/fault/restore/rollback PASS | Это synthetic lab, не публичный LLM-поиск |
| Настоящая модель | Закрытый DeepSeek LIVE eval 24/24 на согласованном synthetic corpus; shared DecisionDeepSeekIntent | LIVE UI→provider→SQL→cards/map ещё не принят; decision-transport-fixture подменяет model transport |
| Provider privacy | `services/ai_provider_privacy.py`: RealUserOutboundDenied отвергает real-user input | Account evidence, разрешённый payload и рабочая minimization/retention policy; ключ сам по себе ничего не включает |
| Реальные данные | Flatio pilot: 73 записи, 8 eligible, pipeline/proof проверены; данные после проверки удалены | Постоянный ingestion и покрытие рабочего каталога этим не доказаны |
| Нагрузка | Population/live-inputs оптимизации уже есть; последний описанный 100k прогон: 1161 ошибок/3600 попыток, 0/18 SLO-pass | ISSUE-004 OPEN; 500k/1m не приняты, browser/HTTP SLO не сертифицирован |
| Голос | `services/ai_voice_execution.py`, `ai_offline_asr.py`: ASR+intent+search в одной durable operation; offline tests | Реальные ASR, microphone UI, HTTP/media validation и browser приёмка; voice=false |
| Saved/rematch | `repositories/ai_saved_searches.py`, migration0074, snapshot/CAS/idempotency/dry-run; UI читает/удаляет существующие записи | Публичное создание, rematch/delivery worker и уведомления; saved_searches=false |
| Выпуск | Runbooks, metrics, retention/erasure journal, isolated migration/restore/kill-switch evidence | Production runtime/config, provider/data/performance gates, инфраструктурная проверка, выпуск и наблюдение |

Основания в проверенном main:

- [Ранее согласованный маршрут](https://github.com/antony502189-max/Ttest/blob/4a60e1632d3b234f4b5321d224b3abfd041769a3/docs/ai-search-developer/AI_CONTOUR_ROADMAP_RU.md).
- [Общая приёмка и открытые gates](https://github.com/antony502189-max/Ttest/blob/4a60e1632d3b234f4b5321d224b3abfd041769a3/docs/reports/AI_RELEASE_ACCEPTANCE_20261101.md).
- [Parser/UI composition](https://github.com/antony502189-max/Ttest/blob/4a60e1632d3b234f4b5321d224b3abfd041769a3/docs/reports/AI_PARSER_UI_COMPOSITION_20261101.md).
- [Outbound boundary](https://github.com/antony502189-max/Ttest/blob/4a60e1632d3b234f4b5321d224b3abfd041769a3/docs/ai-search-developer/DEEPSEEK_OUTBOUND_POLICY_RU.md), [operating policy](https://github.com/antony502189-max/Ttest/blob/4a60e1632d3b234f4b5321d224b3abfd041769a3/docs/ai-search-developer/OPERATING_PRODUCT_POLICY.md).
- [Нагрузка и bottleneck](https://github.com/antony502189-max/Ttest/blob/4a60e1632d3b234f4b5321d224b3abfd041769a3/reports/AI_LIVE_INPUTS_20261031.md), [migration rollout](https://github.com/antony502189-max/Ttest/blob/4a60e1632d3b234f4b5321d224b3abfd041769a3/docs/ai-search-developer/AI_MIGRATION_ROLLOUT_RU.md).
- [Исходный продуктовый scope](https://github.com/antony502189-max/Ttest/blob/d086fec3f0c4286d66493082982e2ac55a14d174/docs/ai-search-developer/01_PRODUCT_SPEC.md) найден в сохранённой docs-ветке, а не в текущем main. Прямые решения владельца учитываются вместе с более поздней operating policy; конфликты нельзя разрешать молчаливым исключением возможностей.

Старые упоминания «#403 draft, merge запрещён» исторические: PR уже merged. Не нужно снова его сливать; merge не доказывает deploy или разрешение публичного запуска. Старый `08_NEXT_ACTIONS.md` — журнал промежуточных веток, не актуальный порядок оставшейся работы.

**Исторический срез PR #404 до исправлений и merge (03.11):** пользователь имел в виду следующий PR [#404](https://github.com/antony502189-max/Ttest/pull/404), а не #403. GitHub: open, draft, merged=false, mergeable=true; head `7f8bbabc0a051d46d9911e51907975aeafc7bb00`, base текущий main4a60e163. На точном head11 workflows success,2 conditional skipped; submitted reviews и review threads отсутствуют. Это подготовка закрытого LIVE-контура, runtime pairing/journal admission/recovery; не публичный запуск AI. В этой сессии проверены metadata/CI, независимое code review113 изменённых файлов не выполнено. Перед включением изменений в основную базу нужны финальное ревью и выход из draft; не считать PR уже слитым. Отчёт PR сохраняет предыдущую реальную LIVE-попытку как FAILED, journal52/$0.575120 reserved; прежние51/56 из старого roadmap не использовать как текущий остаток бюджета. Новые вызовы модели и merge не выполнялись.

## Продуктовый контракт и полная приёмка

| ID | Обязательное поведение | Критерий готовности |
| --- | --- | --- |
| A1 | Текстовый поиск ES/RU/EN: место, бюджет/период, жильцы/вместимость, тип жилья, животные, курение и поддерживаемые удобства | Настоящая модель даёт ожидаемые typed conditions, SQL — ожидаемые IDs и подтверждённые причины; нет выдуманных объектов/цен/процентов |
| A2 | Уточнение меняет только названные условия | Follow-up, отрицания, ambiguity, unknown/conflict, no-change и unsupported проверены; hard не ослабляется молча |
| A3 | Актуальные карточки/карта, пагинация, открытие объявления | Visibility/currentness до count/order/LIMIT, stale/hidden/changed записи исключены. Сохранены существующие TOP/boost, native/external cards, gallery/favorites и long-term cap€1000 |
| A4 | Guest3/auth200 успешных операций в сутки Europe/Madrid, DST | Ошибки/clarification без debit; meaningful ноль при пригодном покрытии — успех и один debit; отсутствие пригодного покрытия — отдельный исход без debit; follow-up — новая операция |
| A5 | Retry/reload/timeout/login/logout/потеря ACK | Exact key/payload, durable receipt, ownership и recovery не допускают двойного model call/debit; guest state не переносится в auth молча |
| A6 | Голос: Send→ASR→intent→SQL→cards без обязательного второго подтверждения | Микрофон/остановка/отмена/ошибки/исправление текста; RU/ES/EN и смешанная речь; ASR+intent=один debit; media containers/codecs/размер/длительность объявлены и проверены |
| A7 | Сохранение AI-поиска после регистрации | Owned committed snapshot; create/retry/list/disable/delete; гость не сохраняет; ручные saved searches работают |
| A8 | Уведомления о новых совпадениях | Rematch worker: fencing/retry/idempotency; live eligibility перед delivery; нет дублей/чужих результатов/отправки после disable/delete |
| A9 | Весь путь доступен из интерфейса | ES/RU/EN, 320/390/768/1440px, loading/empty/error/retry, доступность и восстановление; обычный ручной поиск всегда работает |
| A10 | Подтверждённая скорость | Browser voice p95≤10s Send→paint реальных карточек при исправных провайдерах/типовой сети. Отдельно SQL/map p95≤500ms, p99≤1000ms, 0 ошибок,100k/500k/1m и concurrency50/100/200; протоколы не подменяют друг друга |
| A11 | Готовность эксплуатации | Разрешённый provider/account/payload, реальные coverage/freshness, anti-abuse/cost telemetry, retention/erasure, supervised workers, migrations/backup/restore/kill switch |
| A12 | Реальная доступность на сайте | Подтверждён deployed SHA/capabilities; A1–A11 выполнены в применимых средах; завершены реальный pilot и период наблюдения, нет blocker-дефектов |

**Полное завершение включает A6–A8.** Промежуточный текстовый выпуск возможен, но его нельзя называть готовностью всей функции. Вне scope: вакансии, POI/routes, live transcription/TTS, замена карточек и новые рекламные механики. Месячный жёсткий spending cap ранее не утверждён; anti-abuse и ограниченные бюджеты конкретных тестов сохраняются.

## Порядок оставшихся работ

### S0 — установить исходное состояние

**Готов в части обзора кода и документов.** Проект, main SHA, компоненты, существующие стенды и оставшиеся gates установлены выше. Это не новая runtime-сертификация.

### S1 — закрепить приёмку и рабочую базу

**Готов в пределах критериев выхода S1. Полная продуктовая приёмка A1–A12 не закрыта.**

- [x] S1.0 Ревью PR #404, исправления F1–F8, exact-head CI и подтверждение merge завершены. Владелец слил PR; GitHub и origin/main подтвердили merge SHAece1632e. Исправления доступны в main; post-merge checks и работа deployed версии этим не подтверждены.
- Исполнение S1.0 на03.11: commits `a6fad628`/`546abf7c`/`b709810d`,11 запускаемых workflows success/2 conditional skipped на итоговом PR head. #404 merged владельцем. Реальный LIVE/public rollout не разрешён этой приёмкой.
- [x] S1.1 [Полная матрица](ai-search-developer/AI_SEARCH_ACCEPTANCE_MATRIX_RU.md) + machine-readable JSON + `scripts/ai-search-acceptance.py`: 14 наборов/12 критериев, exact paths/commands/limits/gaps. Закрыт первый локальный пробел A9: ES/RU/EN × 320/390/768/1440, 12 browser cases PASS. Остальные A9 и A6–A8 gaps сохранены.
- [x] S1.2 Чистота existing worktree подтверждена до switch; создана `codex/ai-search-acceptance-matrix` от origin/main `ece1632e`, перенесены канонические план/AGENTS. Старый root checkout и чужие deploy/docs/untracked изменения сохранены.
- [x] S1.3 На merged application source `ece1632e`: targeted177 PASS; матричные offline339 PASS (наборы пересекаются, не суммировать), TypeScript PASS; итоговый общий browser прогон75 PASS (63 прежних +12 новых A9), pairing13 PASS. Первые12 новых cases исправлены после неоднозначного тестового селектора. Python3.12.14/pytest9.1.1/pydantic2.13.4/httpx0.28.1, Node24.22.1/Playwright1.61.1. Post-merge AI frontend и combined PostGIS/HTTP workflows SUCCESS. Все6 post-merge main workflows SUCCESS подтверждены в S2; CI новых изменений отдельно не подтверждён. Локальный первый `.audit-venv` запуск не прошёл collection из-за отсутствующих dependencies; принят повтор на существующем release-venv с PYTHONPATH текущего backend. [Отчёт](reports/AI_SEARCH_S1_MATRIX_20261103.md).

04.11 S1.1/S1.3: по review PR#405 исправлены pytest source-root policy и optimized inventory/status progression. Backend console/root collection восстановлены, lab остаётся исключён из production packages. Новый CI gate рассматривается по текущему PR head, не по старым main success; [подробности](reports/PR405_REVIEW_FIXES.md).

Выход: одна актуальная рабочая база и воспроизводимый набор приёмки без повторной разработки готовых компонентов.

### S2 — рабочий каталог и обновление фактов

**Частично реализован.**

- [ ] S2.1 Частично: создан [source-specific профиль](reports/AI_SEARCH_S2_SOURCE_PROFILE_20261103.md), повторены existing synthetic audit4active records и offline field-capabilities (real_records_measured=0). Real public/eligible/verified/unknown/region/freshness оставлены null; первоначальное разрешённое покрытие ещё не выбрано и не измерено. Не обещать всю Испанию по одному Flatio pilot.
- [ ] S2.2 Частично: presence/content freshness fixes сохранены; bounded coordinator existing primitives реализован в `d596c32e492feae693f8f040e5ccaa1cc883acc6`. Source-filtered claim и captured-name guard защищают mapping, два курсора и лимиты ограничивают tick, refresh_due не продлевает content TTL. Финальные targeted107 PASS, Ruff/mypy PASS. [Coordinator/evidence](reports/AI_SEARCH_S2_COORDINATOR_20261103.md). Durable synthetic supervisor harness реализован в `f76d99a25bbb3800621f97079474985f397a90ba`:153targeted и100lab/1skip PASS (пересекаются), [evidence](reports/AI_SEARCH_S2_SUPERVISOR_20261103.md). Review F-02–F-05: current source-check health согласован с SQL eligibility, pending signals старых receipts сохраняются до exact-receipt ack, queue cleanup не обрывает budget, source grammar едина; runtime source `a31ac490d4eeb3ec8357bfd79fe339b4a7ca1e1f`, [tests](reports/PR405_REVIEW_FIXES.md). Hard process deadline/restart rehearsal локально выполнен в c4b32cb4:88targeted PASS, Ruff/mypy и943inputs provenance PASS; три kill points, recovery checkpoint/receipt/PG lease/fence и отсутствие двойной публикации — отчёт AI_SEARCH_S2_PROCESS_20261104.md. Exact-head Linux CI/review, разрешённый source-specific detail refresh и постоянная supervised цепочка ещё нужны; S2 не закрыт.
- [ ] S2.3 Локальная synthetic часть расширена: исправлены direct403/429/timeout/unknown health и stale presence-refresh;3 новых SQL +4 full-schema HTTP/card/map cases. Финально8quality/32freshness-removal PASS; broader296facts/78integration были до последнего presence split и не выданы за exact-final runs. Retirement/remap/delete/conflict/visibility/fencing покрыты existing tests. Реальные source/data и supervised-chain gates остаются открытыми.

Выход: согласованное измеренное покрытие, воспроизводимо свежие данные и работающий процесс их обновления; A3 и data-часть A11.

04.11 S2.2 detail increment: source `716ae9fa2298c4455ceb6d4392e937a1b8457748`,150targeted и1752unit/16skip PASS (пересекаются), Ruff/mypy175/946inputs PASS. Source-only mock detail, exact receipt/PG atomic effect, CAS/race/rollback/age/capacity и повторный binding guard проверены; implicit ACK отсутствует. [Detail contract/evidence](reports/AI_SEARCH_S2_DETAIL_20261104.md). Pre-HTTP durable budget/lease/fence и lifecycle composition consumer ещё OPEN; real/standing refresh не включён.

### S3 — настоящий текстовый AI

**Частично реализован.**

- [ ] S3.1 Подготовить конкретную provider/account/payload конфигурацию; закрыть real-user outbound gate доказательствами. Не обходить RealUserOutboundDenied и не заменять review наличием ключа.
- [ ] S3.2 Собрать runtime вне test-only lab: secrets на сервере, distributed gates, sessions/quota/execution, maintenance, signing и явное отключение. Не разрешать public AI одной env-переменной без проверенной сборки.
- [ ] S3.3 Согласовать model timeout с execution15s/HTTP20s; выполнить настоящий закрытый UI→provider→SQL→cards/map pilot по разрешённому corpus/бюджету.
- [ ] S3.4 Пройти A1–A5/A9 на ES/RU/EN, расширив прежний corpus24; проверить semantic correctness, отказы и стоимость, а не только JSON schema.

Выход: настоящий текстовый end-to-end, а не fixture transport или отдельный model eval.

### S4 — голос, сохранение и уведомления

**Частично реализован. Обязателен для полного завершения.**

- [ ] S4.1 Реальные ASR transport, microphone/UI/HTTP поверх VoiceSearchExecution, media validation и audio privacy; автоматический первый поиск и один debit.
- [ ] S4.2 Public owned save endpoint/UI поверх RegisteredAISearches. Сохранять committed snapshot, не mutable session; создание, повтор, список, отключение и удаление.
- [ ] S4.3 Rematch worker и delivery: fencing/retry/idempotency, live recheck перед отправкой, background quota/retention, disable/delete и дедупликация.
- [ ] S4.4 Пройти A6–A9 и регрессии ручных saved searches/notifications; включать capabilities только после реальной готовности.

Выход: голос и saved/delivery работают через интерфейс и настоящие зависимости.

### S5 — производительность и итоговое качество

**Открыт; capacity ранее отложен владельцем, ISSUE-004 не закрыт.**

- [ ] S5.1 Убрать повторный обход cohort/массовые wide-proof probes; измерить SQL graph/planning. Начать с bounded correctness и EXPLAIN, не повторять большие прогоны без доказанного выигрыша.
- [ ] S5.2 После выигрыша и требуемого допуска провести свежий exact-SHA capacity protocol с исходными порогами/ресурсами. Не ослаблять proof/freshness/visibility ради скорости.
- [ ] S5.3 Отдельно измерить browser text/voice end-to-end, стоимость, ошибки и стабильность; пройти A10.
- [ ] S5.4 Пройти полную A1–A11 матрицу и применимые lint/types/build/backend/PostGIS/Redis/browser/security regressions; закрыть blocker-дефекты.

Выход: подтверждённые SLO и качество. Старые PASS, быстрые ошибки и repository benchmark не заменяют browser certification.

### S6 — выпуск и эксплуатация

**Публичный выпуск не выполнен.**

- [ ] S6.1 Production-like rehearsal миграций0077–0079 и последующих: locks/WAL/disk/write impact, backup и независимый erasure journal/restore barrier.
- [ ] S6.2 Проверить production provider/data/runtime config, supervisor, alerts и aggregate telemetry без приватного текста.
- [ ] S6.3 Подготовить конкретный release/rollback/kill-switch пакет, пройти exact-main CI и штатный допуск выпуска.
- [ ] S6.4 Закрытый реальный pilot в целевой среде, затем управляемая активация с проверкой deployed SHA и сохранением обычного поиска.

Выход: реальная доступность и эксплуатационные доказательства, а не только merged PR.

### S7 — окончательная приёмка

**Не начат.**

- [ ] S7.1 Пройти A1–A12, сохранить report/evidence и краткую пользовательскую инструкцию.
- [ ] S7.2 Подтвердить стабильность за заранее определённый период и ожидаемую нагрузку.
- [ ] S7.3 Все обязательные пункты закрыты; оставшиеся улучшения явно необязательны. Только здесь писать «AI Search полностью завершён».

Основной маршрут: **S1→S2→S3→S4→S5→S6→S7**. При внешнем блокере можно готовить независимые локальные задачи следующего этапа, указывая ID; это не закрывает заблокированный этап. Готовые synthetic стенды не строить заново.

## Блокеры и условия снятия

| ID | Состояние | Условие снятия |
| --- | --- | --- |
| B0 | СНЯТ: целевой проект найден | Подтверждение пользователя и проверка main03.11 |
| B1 | СНЯТ для разработки: S1.2 выполнен | Новая ветка от ece1632e в проверенном чистом existing worktree; чужие изменения старого root сохранены |
| B2 | Real-user outbound BLOCKED в коде | S3.1: account/data owner, account reference без секретов, проверенные contract/DPA/region/training/retention/deletion/уведомление и minimization. Сначала подготовить reviewable пакет и negative tests, затем запросить только отсутствующие account-сведения |
| B3 | Capacity ISSUE-004 OPEN; большие прогоны ранее отложены | Сохранить A10 обязательным. Подготовить bounded план S5; перед возобновлением явно отложенных больших benchmarks получить конкретное поручение, если его ещё нет в сессии |
| B4 | Нет постоянного доказанного рабочего каталога/покрытия | S2: source-specific профиль, coverage/freshness measurements, update/retirement chain и разрешённый объём ingestion |
| B5 | Voice/saved/delivery не активированы | S4.1–S4.4, реальные providers, background/delivery policies и end-to-end приёмка |
| B6 | Production среда не сертифицирована | S6: инфраструктурные доказательства, exact SHA/CI, подготовленный release и требуемые полномочия. Merge#403 сам по себе блокер не снимает |

Локальную разрешённую подготовку продолжать без повторных общих вопросов. План сам по себе не разрешает новые платные calls, произвольную передачу пользовательских данных, запрещённые ранее большие benchmarks или production activation. До необходимого решения сделать всю независимую работу и предъявить конкретный проверяемый результат.

## Правила продолжения между сессиями

1. Прочитать этот файл; проверить фактические GitHub main, рабочий SHA и изменения. Смена SHA требует сверки затронутых доказательств, а не нового roadmap.
2. Продолжать указанное следующее действие. Каждая задача получает Sx.y и A-критерий; новые идеи идут в отложенный список.
3. После сессии обновить текущую точку, статусы, evidence/точный SHA, блокеры, журнал и одно следующее действие. «Готов» требует критерия выхода, не только сборки.
4. Не смешивать offline service, fixture, closed LIVE eval, merged code и production. Старые test counts не переносить на новый runtime.
5. Порядок/критерии менять по прямому указанию пользователя либо доказанной зависимости, с причиной, влиянием и версией. Не исключать voice/saved/delivery и не снижать SLO ради удобного завершения.
6. Исторические ограничения/approvals проверять по времени и фактам. Не спрашивать повторно уже разрешённое; не сохранять запрет на merge уже merged PR как вечный блокер.

## Журнал

| Дата | Версия/этап | Выполнено и доказательство | Следующий шаг |
| --- | --- | --- | --- |
| 2026-11-04 | 3.3/S2.2 review407 | Source d797e68a: F01–F05/T01–T03 обработаны; RED9fail/2pass, затем1752unit/16skip,402PG/1skip,54cards/map/gallery PASS; Ruff/mypy175/migrations/check/947inputs PASS. F01 — honest trusted dynamic contract, не cryptographic callback attestation. [Отчёт](reports/PR407_REVIEW_FIXES.md). PR остаётся draft, release/data/provider gates открыты | Exact-head Linux CI исправлений и повторная оценка владельцем |
| 2026-11-04 | 3.2/S2.2 detail | #406 merged владельцем в1990638d, независимо проверено. Source716ae9fa: bounded exact-receipt mock detail refresh, source CAS/projection/PG receipt atomicity, no implicit ACK, race/replay/rollback/capacity/binding guards. Unit1752/16skip PASS; финальный targeted150PASS на свежем owned PG после отдельно сохранённого interruption. Ruff/mypy175 и946inputs PASS. [Отчёт](reports/AI_SEARCH_S2_DETAIL_20261104.md). S2 partial, S3–S7 OPEN, activation/deploy отсутствуют | Exact-head CI/review нового detail increment |
| 2026-11-04 | 3.1/S2.2 финальный CI | Head1fe59146:11/11workflows и18/18jobs SUCCESS; полный self-review и6fixes завершены, PR#406 ready/open/not merged. Источник61c4e027; описание PR и локальный CI snapshot фиксируют exact-head доказательства. S2 partial, остальные gates открыты, deployment не выполнялся | После включения#406 вmain продолжить bounded synthetic source-specific refresh contract |
| 2026-11-04 | 3.1/S2.2 review | Полное self-review#406:6RED→GREEN findings исправлены в61c4e027.1729unit/16skip,82PG/coordinator/supervisor,116lab/1skip/8subtests PASS; Ruff/mypy174 и943inputs provenance PASS. Старый17d2857f CI11/11SUCCESS отдельно от нового source. [Отчёт](reports/PR406_REVIEW_FIXES.md); owned PG/volume удалены, activation/merge/deploy не выполнены | Exact-head CI исправлений#406 |
| 2026-11-04 | 3.0/S2.2 | `c4b32cb4d15f4d8bb6dc767618c86ef1f2f750e3`: внешний spawn/kill/join для finite synthetic tick. Реальный coordinator прерван в builder после PG claim, после PG publication и после SQLite receipt; restart/lease/fence/pending signals/no duplicate publication проверены. Final88PASS, Ruff/mypy1file и943inputs provenance PASS; ранний87/1FAIL без root PYTHONPATH сохранён отдельно. [Отчёт](reports/AI_SEARCH_S2_PROCESS_20261104.md). S0–S1 прежние, S2 partial, S3–S7/B2–B6 OPEN; production/provider/budget/data не активированы | S2.2 exact-head Linux CI/review process lifecycle increment |
| 2026-11-04 | 2.9/merge#405 и передача | Владелец слил#405; GitHub merged=true и fetch подтвердили main `20435c2e36cabac5608780fe01ab75e47efe152c`,11:43:09 Europe/Moscow. PR headc2affaf4:11/11workflows,18/18checks SUCCESS. Post-merge6runs:3SUCCESS/3in_progress при передаче, deploy не заявлен. Existing worktree переведён чисто на новую codex/ai-search-process-lifecycle от main; old root/чужие изменения сохранены. Пользователь запросил новый чат Sol/medium/full access | S2.2 process-isolated synthetic deadline/kill/restart code + tests; сверить post-merge CI без подмены доказательств |
| 2026-11-04 | 2.8/S1.1/S1.3/S2.2 review | По прямому запросу владельца исправлены F-01–F-07 PR#405; hypotheses воспроизведены RED, runtime source `a31ac490d4eeb3ec8357bfd79fe339b4a7ca1e1f`. Facts477/1skip, schema119/1skip, quota350, CI-catalog53, browser75/pairing13 PASS; source/overlap caveats и unit1703/16skip в [отчёте](reports/PR405_REVIEW_FIXES.md). Ruff/mypy174 и940inputs PASS, owned PG/Redis удалены. Новый CI должен быть green на текущем head; merge/deploy не выполнялись. S0–S1 прежние границы, S2 partial, S3–S7/B2–B6 OPEN | S2.2 bounded hard process deadline/kill/restart rehearsal после review fixes/current-head CI |
| 2026-11-03 | 2.7/S2.2 | Durable synthetic supervisor harness, source `f76d99a25bbb3800621f97079474985f397a90ba`:153targeted PASS,100lab PASS/1skip (пересекаются), Ruff/mypy и939runtime inputs provenance PASS. Atomic rollback, process exit claim recovery, lost ACK, fencing, backoff/deadline, health/terminal jobs; owned PG удалён. Draft PR#405 создан; новых CI/merge/deploy PASS не заявлено. [Отчёт](reports/AI_SEARCH_S2_SUPERVISOR_20261103.md). S0–S1 прежние, S2 partial, S3–S7 и B2–B6 OPEN | S2.2 bounded process-isolated synthetic coordinator/journal deadline/kill/restart rehearsal |
| 2026-11-03 | 2.6/S2.2 | Bounded coordinator + source mapping race guards, code `d596c32e492feae693f8f040e5ccaa1cc883acc6`; финальные targeted107 PASS, Ruff/mypy4app files PASS,936runtime inputs provenance PASS; broader506PASS/1skip до final capture guard, не exact-final certification; disposable PG удалён. [Отчёт](reports/AI_SEARCH_S2_COORDINATOR_20261103.md). Реальные источники/provider/production/capacity не активированы; S0–S1 прежние статусы, S2 partial, S3–S7 и B2–B6 остаются открытыми | S2.2 local synthetic supervisor harness: durable receipt+checkpoint/CAS, restart/backoff/deadline/health |
| 2026-11-03 | 2.5/S2.2–S2.3 | Исправлены direct-check health и presence/content freshness. Финально8SQL +32integration PASS;114unit/1skip, broader296facts/1skip и78integration отмечены как промежуточные до presence split. Миграции только в disposable PG/PostGIS. Main ece1632e:6/6 workflow SUCCESS; новый head CI/deploy не заявлен. Paid/source/outbound/journal/production/capacity не выполнялись | S2.2 bounded coordinator existing primitives/recovery/supervision seam; real S2.1 measurements открыты |
| 2026-11-03 | 2.4/S1.1–S1.3 | Подготовлена актуальная ветка, исполнимая A1–A12 матрица и CI inventory check; 339 offline, 63 прежних browser, 12 новых A9 и 13 pairing PASS; targeted177 пересекается. Post-merge AI workflows SUCCESS, общий Full audit ещё выполняется. S2.1: existing offline audit4active synthetic records и source/field профиль, real metrics=null,7audit tests PASS. Provider/journal/production/ingestion/capacity не менялись | S2.1 профиль начат; далее S2.2–S2.3 synthetic fault chain, real measurements остаются открытыми |
| 2026-11-03 | 2.3/S1.0 закрыт, передача | Владелец сообщил о merge#404. GitHub подтвердил merged=true,03.11 в16:42:08 Europe/Moscow, merge SHAece1632e2872240a36646ddf0b2518a027d67d84; git fetch подтвердил тот же origin/main. PR headb709810d ранее прошёл11 workflows/2conditional skipped. По запросу пользователя продолжение передаётся в новый чат GPT‑6.1 Sol/medium | S1.1: полная матрица A1–A12; prerequisite S1.2 перед правками, затем S1.3 merged-main checks |
| 2026-11-03 | 1.0/S0 | Создан предварительный план/AGENTS. Осмотрен только старый checkoutf7845b16; AI в нём не найден. Вывод был неполным | Проверить ветки и актуальный репозиторий |
| 2026-11-03 | 2.0/S0→S1 | Пользователь подтвердил112233.es. Через GitHub подтверждён main4a60e163/merged#403. Изучены актуальный roadmap, policies, release/parser/capacity evidence, UI/runtime/execution/voice/saved и исходный scope. Общий план заменён конкретным остаточным маршрутом; B0 снят. Новые runtime tests, paid calls, crawling и deployment не выполнялись | S1.1: оформить исполнимую полную матрицу на existing fixtures/drivers; затем S1.2–S1.3 |
| 2026-11-03 | 2.2/S1.0 | Получен пользовательский внешний review PR404 на7f8bbabc. F1–F8 исправлены в изолированной копии ветки: closed access/mTLS, manifest coverage, attestation recovery, namespace/WS, private journal/process fencing, signed operational evidence, единый spec и log severity. Локально1755 backend/73 Linux/13 lab browser/63 main browser PASS; отдельно настоящий nginx mTLS и build matrix. [Отчёт и ограничения](reports/PR404_REVIEW_FIXES_20261103.md). Реальные provider/journal/production не менялись | Exact-head CI и итоговый diff; merge по следующему поручению пользователя |

## Изменения маршрута и отложенное

- **3.2→3.3:** прямое поручение владельца — исправить внешнее review#407. Изменения ограничены подтверждёнными findings и отсутствующими регрессиями; known pre-HTTP/lifecycle/product gates не подменены новыми улучшениями или readiness claims.
- **3.1→3.2:** владелец слил#406, пользователь поручил продолжать основной план. Реализован следующий source-specific synthetic detail seam на existing primitives; operation receipt не подменяет future pre-HTTP budget/leases или реальные source permissions. Маршрут и A1–A12 сохранены.
- **3.0→3.1:** прямое поручение владельца — полное ревью и исправления#406 перед продолжением S2. Шесть воспроизведённых проблем закрыты локально; production/data/provider/performance gates и A1–A12 не ослаблены.
- **2.9→3.0:** выполнен следующий локальный S2.2 hard process rehearsal на existing coordinator/journal/PG primitives. Готовность локального кода отделена от Linux CI, постоянной supervision и deployed release. Следующий gate — exact-head CI/review этого increment; S2–S7 и A1–A12 не ослаблены.
- **2.8→2.9:** владелец слил#405; merge независимо проверен. Review gate снят для merged кода, deployment/data/provider/product gates не менялись. Следующий S2.2 остаётся прежним; продолжение передаётся в новый чат по прямому запросу пользователя.
- **2.7→2.8:** прямой запрос пользователя поставил устранение review PR#405 перед следующим локальным rehearsal. Исправлены подтверждённые import/health/backlog/liveness/identity/inventory дефекты и CI disposable-DB compatibility. Основной маршрут и A1–A12 не изменены; synthetic code, Linux CI и release по-прежнему разделены.
- **2.6→2.7:** реализован следующий локальный S2.2 increment supervision, а не новая архитектура. Отдельный owned synthetic journal не является budget journal. Cooperative deadline и hard process lifecycle разделены; следующий rehearsal закрывает оставшийся локальный lifecycle gap. Критерии A1–A12, реальные data/provider и production gates сохранены.
- **2.5→2.6:** следующий локальный increment S2.2 реализован на existing primitives, без новой конкурирующей архитектуры или activation. Добавлены source-name guards для безопасного mapping и documented supervisor contract; реальные measurements и постоянная supervised цепочка не закрыты. A1–A12 и маршрут S2–S7 сохранены.
- **2.4→2.5:** S2.2–S2.3 продвинуты конкретными freshness fixes и synthetic regression evidence. Presence и content checks разделены без новых migration/activation flags. Маршрут S2–S7 и критерии A1–A12 сохранены; S2 не закрыт.
- **2.3→2.4:** выполнены S1.1–S1.3; следующий этап S2 по прежнему маршруту. Добавлены исполнимая инвентаризация и первый A9 locale/viewport contract; A1–A12 и внешние gates не ослаблены. Все локальные результаты отделены от post-merge CI и deployment.
- **2.2→2.3:** владелец слил #404; слияние независимо подтверждено GitHub и fetch. S1.0 закрыт, продолжение — S1.1 с prerequisite S1.2 перед изменениями исходников. По прямому запросу следующий чат создаётся на GPT‑6.1 Sol / medium. S2–S7 и A1–A12 не изменены.
- **2.1→2.2:** S1.0 продолжен по полученному внешнему ревью. Порядок S2–S7 и A1–A12 не изменены; код, инструкции и единый план переносятся в ветку #404 одним набором. Локальные проверки не заменяют exact-head CI или LIVE admission.
- **2.0→2.1:** после уточнения пользователя про PR #404 добавлен S1.0 перед выбором рабочей базы. Причина: #404 содержит продолжение того же AI-контура и ещё находится в Draft; его изменения нельзя считать слитыми или начинать разрабатывать повторно. Следующий результат — конкретное ревью/исправления/exact-head проверки. Порядок S2–S7 и критерии A1–A12 сохранены.
- **1.0→2.0:** исправлена устаревшая исходная точка; учтены реализованные компоненты/исторические проверки. Схема S0–S7 сохранена, задачи конкретизированы. Голос и saved/delivery включены в полное завершение по найденному scope. Прежние SLO и ISSUE-004 сохранены.
- Необязательные улучшения: пока отсутствуют. Вакансии, POI/routes и TTS вне scope.

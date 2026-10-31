# Закрытый текстовый synthetic стенд

Только пункт 1 roadmap. Реальные React UI/FastAPI/PostGIS/Redis и прежние
repositories/services; тестовые подмены только вместо intent model и extraction.
`SyntheticParser` — конечный список точных фраз, **не LLM**. Извлечение — явно
созданные синтетические FactBatch с цитатами. Карточки и маркеры берутся из SQL.
Это не проверка качества модели, capacity или разрешение public AI.

## Запуск в этом worktree

PowerShell 7, Docker Desktop, Node.js, tar, установленные frontend dependencies.
Работать в `C:\Users\HONOR\.codex\worktrees\main-integration-audit\Ttest`.
Исходный checkout в Documents не использовать. Ветка `codex/post-merge-remediation`.

```powershell
git status --short                    # изменения должны быть committed
./scripts/ai-text-lab.ps1 start        # build → DB/Redis → TLS → migrate → seed → UI/API ready
./scripts/ai-text-lab.ps1 status
./scripts/ai-text-lab.ps1 seed         # проверенный no-op после полного seed
node scripts/smoke-ai-text-lab.mjs     # реальный Chromium, без page.route/API mocks
node scripts/check-ai-text-lab-isolation.mjs # topology + shared gate + own Redis stop/recovery
./scripts/ai-text-lab.ps1 stop         # только четыре собственных service, volumes сохраняются
```

Launcher использует `git archive HEAD`, собирает frontend из snapshot и копирует
backend из него в image. `output/ai-text-lab/source.json`, `/build-info.json` и
labels контейнеров фиксируют source SHA. Незакоммиченные файлы не попадут в стенд.
Воспроизведение прежнего source: использовать checkout нужного commit в этом
разрешённом worktree, сохранив новые коммиты; reset/rebase на origin не нужен.

По умолчанию используются уже имеющиеся dependency images
`ttest-main-audit-backend:7d4c1255` и `ttest-main-audit-frontend:7d4c1255`.
Их **код полностью перекрывается** кодом snapshot / новым dist.
Backend lab image также переустанавливает runtime dependencies по текущему
`backend/constraints.txt` и выполняет `pip check`; старый cached dependency
не может обойти обновлённый lock.
На другой машине
сначала собрать базовые images стандартными `backend/Dockerfile` и `Dockerfile`,
затем передать `-BackendBase <image> -FrontendBase <image>` launcher. Для Node
нужны dependencies из package-lock (`npm ci`, если npm доступен). В отчёте
фиксируются фактические dependency/image версии; локальный smoke не заменяет CI.

## Адрес и TLS

UI и API: `https://localhost:9443`. Единственный опубликованный порт:
`127.0.0.1:9443 → frontend:8443`. Backend:8000, PostgreSQL:5432, Redis:6379
доступны только в отдельной internal Docker-сети. Чужие ttest-сервисы не нужны.
Порт снаружи компьютера не слушается. Никакой внешний deploy не выполняется.

Локальный self-signed сертификат с SAN localhost/127.0.0.1 создаётся на 30 дней
в отдельном TLS volume. Автоматический Chromium smoke явно допускает этот
сертификат для тестового подключения; Secure/HttpOnly/SameSite=Strict cookies,
Origin/CSRF и ownership остаются настоящими. Для ручного браузера потребуется
осознанно доверенный локальный сертификат; launcher не меняет доверие ОС.
Сертификат можно экспортировать: `docker cp
ttest-ai-text-lab-frontend:/lab-tls/localhost.crt output/ai-text-lab/localhost.crt`.
Это не production PKI. Signing keys в модуле и пароль БД — опубликованные
synthetic значения; их нельзя применять в других окружениях.

Nginx сохраняет Host с портом, API вызывается same-origin. CSP разрешает
`connect-src 'self'`, внешние изображения заменены локальной schematic-заглушкой
только в lab build. AI-карта — локальная координатная сетка Adeje с реальными
маркерами `/results/{ref}/map`, pan/zoom и выбором ID, без внешних тайлов и ключей.
Обычная production карта и обычный поиск сохраняют существующий код.

## Пользователи и запросы

Гость получает подписанную Secure cookie после `/identity`; квота — прежние
3 успешных операции в сутки Europe/Madrid. Синтетические пользователи
`user@synthetic.example` (tenant) и `host@synthetic.example` (host), пароль
`Synthetic-Lab-Only-2026!`, email_verified=true. Вход — обычный `/auth/login`;
auth quota — прежние 200/сутки. Это только локальные тестовые учётные записи.

На главной нажать «Escribir mi búsqueda», выбрать `Usar el modo de inicio:
Larga estancia`. Фразы обрезаются по краям и сравниваются без учёта регистра:

| Фраза | Изменение typed intent | Ожидание на исходном наборе |
|---|---|---|
| `все варианты` | снять все критерии кроме явно выбранного rental_mode | 4 карточки |
| `с маленькой собакой` | hard pets: small dog ×1 | 2 карточки |
| `до 600 евро в месяц` | hard budget: 600 EUR/monthly | после собаки 1 карточка |
| `до 400 евро в месяц` | hard budget: 400 EUR/monthly | 0 карточек |
| `без ограничения бюджета` | remove budget, сохранить pets и остальные условия | после собаки 2 |
| `желательно с балконом` | soft balcony=true | soft не исключает неизвестное |
| `обязательно с балконом` | hard balcony=true | 0: нет подтверждения |

Другие фразы завершают operation как `failed/LLM_FAILURE` без списания; это
существующее обозначение ошибки parser boundary, а не свидетельство вызова LLM.
Уточнения сохраняют остальные typed conditions. После трёх успешных guest
запросов новый запрос получает 429. Чтения cards/map/results и replay не списывают
квоту. Новая сессия не обнуляет квоту. Для дальнейшего ручного прогона войти
синтетическим пользователем или использовать новый отдельный guest context.

## Каталог и настоящая цепочка

IDs детерминированы UUIDv5, namespace `295a49e5-0159-4e34-9bb1-b6023aeb902c`.
Семь синтетических Listing + ExternalListingSource, затем для каждого:
`FactPipeline.observe → claim → complete → facts/projection → QueryProofs.prepare`.
Ни карточки, ни proof rows напрямую не вставляются. После подготовки deliberately
меняются source, visibility и price, поэтому старые proofs не разрешают выдачу.

| Случай | ID | Исход |
|---|---|---|
| allow-500 | `0f721c39-b8cf-5879-bea1-522514de63d1` | собака разрешена; 500 EUR/monthly |
| allow-700 | `a242160c-aa54-5e29-bde3-9a53ac8b5674` | собака разрешена; выше 600 |
| deny-450 | `a9fa78c3-7515-5a80-bb79-4bc5770c0e03` | явный запрет pets |
| unknown-550 | `36c2741e-0d7c-5610-bbbe-19f32de52155` | неизвестные pets не становятся allow |
| stale-510 | `29d213f8-efc4-5545-af7f-a41a1bfdc08b` | изменён raw source после prepare; исключён |
| hidden-520 | `3affab0b-45b7-5c44-bcb5-13cc285338af` | скрыт после prepare; исключён |
| price-changed-530 | `4300e4c1-e51e-5847-a146-a1c2a608584c` | canonical цена 900 после prepare; исключён |

Повторный seed проверяет полный набор IDs, семь succeeded jobs и семь proofs;
при неполном/чужом каталоге отказывается перезаписывать. Данные не очищаются.

## Изоляция и зависимости runtime

Отдельный composition root `uvicorn lab.ai_text:create_app --factory` проверяет
test env, точные DB/Redis/origin и запрет provider credentials. Startup проверяет
comment marker выделенной БД. `app.main:app` сам runtime не создаёт — даже с теми
же env/keys. Старый OfflineDeepSeekIntent и его MockTransport-барьер не изменены.

Явно собраны QuotaLedger, SearchSessions, FactPipeline, VerifiedCardSearch,
TextSearchExecution, guest/cursor signing, RedisRateLimiter, AIAttemptGate и HTTP
gate. В AI gates нет memory fallback: Redis outage даёт закрытый отказ. Политики
стенда: HTTP 20 s, 32 KiB body, 5 active sessions, 3600 s session/guest lifetime;
HTTP/IP 240/min, issue 12/min, session create 20/min, parser attempt 12/min;
quota lease 60/60/grace30 s; SQL 5 s, pool wait30 s, lock2 s. Это bounded test
policies, не утверждённые product defaults и не capacity SLO.

Ресурсы: четыре контейнера `ttest-ai-text-lab-{postgres,redis,backend,frontend}`;
volumes `ttest-ai-text-lab-pg-v2`, `ttest-ai-text-lab-{redis,tls,media}-v1`; сети
`ttest-ai-text-lab-network` (internal) и `ttest-ai-text-lab-loopback` (только TLS
frontend). Launcher проверяет label `es.ttest.purpose=ai-text-synthetic-lab-v1`
до мутаций; при коллизии отказывается. Сети/volumes управляются launcher и
объявлены Compose external, чтобы смена source labels не пересоздала данные.
Это локальные lifecycle resources, не внешняя инфраструктура. stop не удаляет
volumes и не использует down/remove-orphans/prune. Capacity/audit/shared DB
не переиспользуются. Backend не подключён к egress-сети; модель/источники/ASR,
workers, real crawl/backfill, платежи/уведомления не запускаются.

Smoke сохраняет `output/ai-text-lab-smoke/result.json` и PNG. Полная матрица
этапа 2, release/public activation и performance остаются отдельными задачами.

# Закрытый intent provider: offline результат пункта 4

1 ноября 2026, Europe/Moscow.

**OFFLINE PASS; LIVE NOT RUN / NOT AUTHORIZED. Пункт 4 целиком не выполнен.**
Владелец явно выбрал «Пока только offline, живые вызовы не разрешаю».
Ни одного обращения к настоящей модели не выполнено; её качество, реальные
token usage, billing и provider latency не измерены. Предложенный набор из 24
запросов ещё не утверждён для live. Mock/TLS fixtures не являются моделью.

## Реализованный результат

Code/test source: `24cf7d09aff5b6c4ee66d23d4d649c81c3f5d517`, существующая ветка
`codex/post-merge-remediation`, draft [PR #403](https://github.com/antony502189-max/Ttest/pull/403).
Работа только в audit checkout; исходный dirty checkout не изменялся.

- Отдельный `ClosedDeepSeekIntent`: настоящий HTTPX HTTPS transport к фиксированному
  DeepSeek endpoint, TLS CA/hostname verification, без env proxy/redirect/скрытых
  retries. Не регистрируется в `app.main`, settings или публичных routes.
- Прежний offline adapter продолжает принимать только MockTransport. Вынесение
  system prompt в переопределяемый метод сохраняет прежний offline wire contract.
  Production AI default disabled; offline UI lab отклоняет новый тип test key.
- Timeout/retry/deadline/response bounds; durable SQLite budget резервирует
  каждую попытку до IO, включая ошибки и retries, без refund при неопределённом
  ответе. Проверяет usage; overrun блокирует дальнейшие обращения. Нет текстов,
  secrets или provider bodies в journal/evidence.
- Strict decision: patch / clarification / no_change / unsupported. Модель
  выбирает только typed search requirements. Identity/version серверные;
  SQL/quota/listings/evidence вне model output. Merged-state и no-op guards
  прежнего adapter переиспользуются.
- Exact synthetic outbound allowlist, 24 RU/EN/ES и mixed examples, эталоны,
  scorer сравнивает весь конечный intent и отдельно отклонение спорных запросов.
  Валидный JSON с неверным price period заведомо проваливает semantic score;
  network failure не засчитывается как смысловой отказ.
- Reproducible PowerShell Prepare launcher: clean exact HEAD archive, pinned
  dependency image, source/corpus/archive hashes, отдельный контейнер с
  `--network none`, без key/DB/host ports. Evidence не перезаписывается.

Контракт, тексты, proposed limits и команды:
[AI_INTENT_MODEL_LAB_RU.md](../docs/ai-search-developer/AI_INTENT_MODEL_LAB_RU.md).
Состав corpus не менялся при фиксации LF; его стабильный Git/Windows SHA-256:
`7b722ab6caa0bf3377a0ace8fcddecf6daa7f7cb9bcebec515ab0cac9997d288`.
Отдельный `.gitattributes` rule сохраняет эти bytes при checkout на Windows.

## Проверки точного source

Локально из archive code source в dependency image
`sha256:1ff5de84b825934599a53fd69add14bb6784d6399a1464e4a38255b2d234a902`:

- Ruff `app tests lab/intent_eval.py lab/test_ai_text.py` — PASS.
- mypy `app`: 156 source files — PASS.
- Unit `-m 'not integration'`: **1596 PASS, 39 optional/platform SKIP**.
  1007 integration-marked cases deselected; PG/integration заново здесь не запускались.
- Explicit lab guards: **5 PASS, 7 subtests PASS**. Включён default-disabled
  application boundary и отказ offline lab при наличии test provider key.
- В unit suite **30 новых closed-provider/evaluator tests**: минимизация,
  gate-before-IO, activation/key/hash guards, retries/reservation/restart,
  concurrent budget writers, malformed/missing/overrun usage, cancellation,
  decision schema/refusal/truncation/identity/no-op, ложное semantic принятие,
  фиксированный HTTPS destination и настоящий локальный TLS wire.
- TLS fixture использует реальные sockets/HTTPX/сертификат в loopback внутри
  контейнера без внешней сети. Доверенный сертификат и два parse проходят;
  недоверенный отклоняется. Test-only backend перенаправляет соединение локально;
  приложение не получает URL/DNS/TLS overrides.
- Настоящий Prepare launcher из чистого `d00833a8` PASS: `live_calls_made=0`,
  бюджетный journal отсутствует, key не читается. Метаданные exact source/image
  и план сохранены в evidence. Следующий `24cf7d09` меняет только импорт CLI
  в тесте; provider/CLI/launcher/corpus bytes идентичны.

Первый диагностический экспорт на Windows выявил CRLF conversion в `git archive`;
launcher теперь явно использует `git -c core.autocrlf=false archive`. Полные
итоговые проверки относятся к исправленному exact source. Все 465 backend files
(430 Python) сверены с Git blobs; строки доказательств и schema не нормализуются
задним числом.

[Машиночитаемый итог](ai-intent-model-evidence/summary.json),
[source и hashes](ai-intent-model-evidence/source.json),
[unit JUnit](ai-intent-model-evidence/unit.xml),
[lab guards](ai-intent-model-evidence/lab-guards.xml),
[Prepare plan](ai-intent-model-evidence/prepared-plan.json),
[SHA256SUMS](ai-intent-model-evidence/SHA256SUMS).

Первый CI на `d00833a8` обнаружил ошибку collection нового теста: консольный
`pytest` не включает `backend/` в sys.path и не видит непакетную папку `lab`.
`24cf7d09` загружает test-only CLI по точному file path, как другие toolchain
tests. Lab не включается в application package и глобальный import path не
меняется. Итоговый локальный unit-прогон выполняется через консольный `pytest`
с app-only import boundary; это исправление не проверяется лишь прежним
`python -m pytest`. Снимок первого CI сохраняется отдельно, не называется PASS.

Новые CI после публикации исправления не объявляются завершёнными заранее.
Прежние 11/11 зелёных workflows других SHA не переносятся на этот source.
Локальная offline проверка не объявляется PG/browser/production сертификацией.

## Остаётся вне результата

До нового явного разрешения и отдельного тестового ключа live запуск запрещён.
После разрешения потребуется заново сверить цены/модель/политику, утвердить
corpus/эталоны и outbound payload, выполнить ограниченный прогон и разобрать
ошибки смысла. Резерв по token admission estimate не является гарантией
верхнего billing провайдера; отдельный ограниченный аккаунт обязателен.

CLI готовит только parser/evaluation contour. Настоящие UI/HTTP clarification
flows, живые failure scenarios провайдера и качество обобщения ещё не приняты.
Настоящий ingestion/crawling — отдельный пункт 5, здесь отсутствует.

Пункты 1–2 сохраняют прежнюю функциональную приёмку на своих SHA. Пункт 3
пропущен по поручению владельца, не выполнен; **ISSUE-004 OPEN / capacity BLOCKED**.
Новые нагрузочные эксперименты не запускались. Старые capacity/audit DB/raw
artifacts и чужие контейнеры не менялись. Merge, public AI, production DB,
ASR, crawling, payments/notifications/Pages/deploy не выполнялись.

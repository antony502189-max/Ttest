# PR404 — исправления внешнего ревью от 03.11.2026

Основание: пользовательский `PR404_review_2026-11-03.md`, SHA256 `d2952014e1df7c9d233495e030a807f30bba6271dd7d848fd1a5b27ff877dd85`. Проверенный исходный PR head: `7f8bbabc0a051d46d9911e51907975aeafc7bb00`, ветка `codex/closed-live-ui-preparation`.

Это исправления preparatory lab-only кода. Merge и реальный LIVE smoke не выполнялись этой работой. Нет новых платных calls, реальных ключей, изменения исходного budget journal, production/crawl/backfill или больших benchmarks. Предыдущая реальная LIVE-попытка остаётся FAILED; известная история52/$0.575120reserved сохранена как история, не перепроверена чтением настоящего журнала.

## F1–F8

| Finding | Исправление | Проверка / предел доказательства |
| --- | --- | --- |
| F1 | RuntimePairing явно отделён от авторизации. Закрытый nginx требует operator mTLS; backend ClosedSmokeAccess проверяет приватный 256-bit proxy token, который браузер не получает. Override подключает отдельные read-only CA/include mounts | ASGI: свежая публичная аттестация и все pairing headers без credential дают403 до обработчика. Реальный nginx с новым конфигом: anonymous400, чужой certificate400, trusted operator200. Только proxy access, не LIVE model acceptance |
| F2 | Полный versioned runtime manifest из reviewed boundary: целые backend/src/scripts/deploy/public/.github и корневые configs/build files. Неизвестный top-level tree отклоняется; добавление/изменение/удаление входа отвергается. CI запускает эту проверку на каждом PR. Исторический artifact directory сверяется целиком с SHA256 manifest |933 входа. Регрессия настоящего verifier: ранее не учтённая зависимость и изменённый Dockerfile отвергаются. Исторические hashes сохранены. Новые изменения НЕ наследуют Docker PASS старого runtime; `historicalEvidenceAppliesToCurrentRuntime=false`. Добавлен независимый read-only container inspector для actual image IDs/digests/environment/mounts/ports; он не выдаёт metadata за пройденный full-stack тест |
| F3 | Все ошибки attestation transport/JSON/abort/timeout нормализованы как503 temporary unavailable; release mismatch остаётся временной недоступностью |13 browser contracts PASS: mismatch, request race, connection refused, malformed JSON,500, abort, timeout, restart сохраняют pending locator и не создают новый POST |
| F4 | Защищён также точный корень AI namespace; WebSocket во всём namespace явно закрывается1008 | HTTP/root/subpaths/repeated-slash и WS negative tests. В реальном nginx конфиге proxy_pass без URI suffix сохраняет исходный путь; альтернативных inference routes не добавлено |
| F5 | На Linux journal/parent directory проверяются на owner UID и отсутствие group/other write; symlink/non-regular file отклоняется. Исходная path/device/inode проверка сохранена. Требуется dedicated trusted UID/private mount | Linux ownership regression и отдельные процессы + restart PASS. Это исключение недоверенных directory writers, **не** заявление об атомарном SQLite file-descriptor binding. Trusted same-UID process/host admin остаются вне модели угроз; условия описаны в runbook |
| F6 | Требуется actual operational-review artifact с хешем из signed admission, source/account/billing scope/reviewer, временем и отдельными подтверждениями cap/credentials/egress/access/journal permissions. Host CLI и factory проверяют его до provider key. Планируемая суммарная reservation не может превышать signed external cap | Wrong hash/source/cap, missing confirmation, expired/naive timezone/extra fields отвергаются. Review покрывает срок signed admission. Реальная provider billing настройка проверяется custodian вне программы; автоматическая независимая billing validation не заявляется. Пока подтверждений нет, LIVE заблокирован |
| F7 | Единый frozen SmokeSpec версии ai-closed-ui-experiment.v1: corpus, cases, baseline/fence и reservation. Authorization, parser, fake matrix и fixtures используют его |Consistency test сверяет corpus/case order/reservation с реальным provider budget policy. Новые эксперименты требуют явной версии/review |
| F8 | Sanitized2xx status теперь INFO, отказы WARNING |Logging regression проверяет severity и отсутствие text/token/body |

Runbook: [закрытый допуск и ограничения доказательств](../ai-search-developer/PR404_CLOSED_LIVE_ADMISSION_RU.md).

## Выполненные локальные проверки

| Набор | Результат |
| --- | --- |
| Backend unit + targeted lab (Windows, без integration) |1755 passed /17 skipped /1041 deselected; 95.84s |
| Linux isolated lab/decision/F1–F8 |73 passed; готовый tools image, user1000, network none, source read-only;5.88s |
| Дополнительные pairing/recovery browser contracts |13 passed;45.4s |
| Основные AI/cards/map/saved browser contracts |63 passed;2.2min |
| Настоящий nginx/mTLS |config test PASS; anonymous400/untrusted400/operator200; только disposable certs, backend не запускался |
| Build matrix |3 настоящие сборки +2 отклонённые некорректные конфигурации PASS; production strips lab flags |
| TypeScript, source i18n, Ruff lab/scripts, mypy app172 |PASS |
| Общий Oxlint |exit0; существующие warnings сохранены |
| Полный manifest и historical artifact verification |PASS;933 входа, старые raw evidence не изменялись |

Числа пересекаются и не суммируются. Backend integration/real PostGIS/Redis сценарии текущим локальным unit прогоном не объявляются пройденными. Настоящий nginx тест использовал прежний immutable nginx image и **новый конфиг по SHA256**, не выдаётся за новый frontend/backend image или полноценный LIVE stack.

В первом Linux запуске на runtime image отсутствовал pytest; этот запуск не принят. Повтор выполнен на существующем tools image `1ff5de84b825934599a53fd69add14bb6784d6399a1464e4a38255b2d234a902`, без package install/pull. Первоначальные async тесты в Windows sandbox остановлены на заблокированном служебном socketpair; успешные прогоны выполнены вне sandbox. Browser contracts на изолированной копии использовали установленные зависимости через junction; Vite сообщил о недоступных font assets вне serving allowlist, все функциональные assertions прошли. Это не visual/layout certification.

В [evidence summary](pr404-review-fixes/validation.json) записаны результаты и hashes сохранённых проверок; [runtime inputs](pr404-review-fixes/runtime-inputs.json) связывают код в содержащем этот отчёт commit с проверенной рабочей копией. Новые CI должны пройти на точном опубликованном head; CI предыдущего7f8bbabc не переносится на эти изменения. Старый Docker runtime72468b2e остаётся только историческим evidence.

Проверка опубликованных Git objects после первого коммита нашла CRLF→LF нормализацию трёх новых raw artifacts. Для новой evidence directory добавлено `-text` в .gitattributes; исходные bytes и SHA256 сохранены, не пересчитаны под изменённый лог. Runtime manifest обновлён с учётом самого .gitattributes. Прежние исторические evidence не менялись.

Первый exact-head combined CI прошёл backend unit1692/7skip, затем остановился на DTZ005 в новом негативном тесте naive datetime. Динамический datetime.now() без tz заменён фиксированной некорректной ISO-строкой; проверка отказа сохранена. Пропущенные после lint шага PostGIS/browser проверки не объявляются пройденными; требуется новый полный run.

## Предел готовности

Для слияния исправлен preparatory scope F1–F8; перед merge нужны новое exact-head CI и итоговый просмотр diff. Это не разрешение real LIVE: independent custody/account cap/egress, точный signed release, реальные user-data/privacy/catalog/migration/capacity gates сохраняются. Полный AI Search остаётся в [едином плане](../ai-search-completion-plan.md), текущий шаг S1.0.

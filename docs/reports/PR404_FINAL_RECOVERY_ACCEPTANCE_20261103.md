# Финальная приёмка PR404: runtime pairing и recovery

Финальный runtime **72468b2e72bef1deeae7bfb18dee22de4e3c7baf**, clean immutable
git archive, `https://localhost:9443`. Это дополнение к
[исправлениям всех9 замечаний](PR404_REVIEW_REMEDIATION_20261103.md), а не
перезапись предыдущих evidence. Реальных provider calls в этой работе **0**.

## Дополнительный найденный дефект и исправление

Новый lab guard первоначально возвращал клиенту ApiError409. При несовпадении
релиза во время status recovery это ошибочно превращалось в окончательный отказ
и удаляло durable locator неопределённой операции. Два новых browser regressions
воспроизвели потерю locator: mismatch самого attestation и race409 между
attestation/запросом. Это было поведение новой границы, не provider failure.

Теперь frontend представляет LAB_RUNTIME_MISMATCH как временную503 как при
preflight, так и при отказе backend. Locator и неопределённость сохраняются,
новая inference не выполняется. Backend продолжает409 до identity/session/parser
для непарных запросов; это не утверждает состояние прежней операции.
Обычные409/conflict и auth/ownership ошибки не изменены.

## Финальные результаты

| Набор | Результат |
| --- | --- |
| Lab pairing/recovery Playwright |7/7 PASS, включая оба новых locator regressions |
| Существующие HomeAI browser contracts на исправленном frontend |56/56 PASS |
| Real HTTPS/UI/backend/PG/Redis recovery с fixture model |15/15 PASS |
| Closed factory + реальные PG/Redis, MockTransport |3/3 PASS |
| Fake LIVE backend + fixture frontend |UI writes0, backend409, fake attempts0 |
| Fixture backend + LIVE-labelled frontend |UI writes0, backend409 |
| Fake LIVE backend + LIVE-labelled frontend |3/3 PASS, один fake attempt/case, replay/reload без повторной inference |
| Provider/lab/boundary regressions (backend tree не менялся) |88 passed /8 subtests |
| Полный backend unit (app/tests не менялись) |1683 passed /16 skipped |
| TypeScript/i18n, ранее проверенные Ruff/mypy172/build matrix |PASS |

Числа не суммируются. Backend/app/test inputs остаются прежними; новый frontend
и оба новых regressions повторно исполнены. После последнего изменения frontend
реальная упаковка и recovery прогнаны заново на указанном source. Последующие
коммиты меняют только отчёт/evidence/CI artifact metadata; CI verifier проверяет
равенство runtime input trees/blobs финального checkout испытанной сборке.

Многократный guest packaging повтор достиг штатного hourly issuance limit.
Guest-run сохранил2 успешных fake cases и завершился без PASS на третьем;
лимиты/бюджеты/счётчики не сбрасывались. Положительная финальная матрица заново
исполнена на существующем **synthetic auth-account** через реальный UI login.
Не выдаём её за повтор guest issuance или за настоящий DeepSeek smoke. Guest3
quota/ownership проверены отдельным 15-case suite. Неуспешные вспомогательные auth
drivers (bootstrap/session hint и ожидание networkidle) сохранены в output;
финальный driver использует штатный UI login и явную readiness.

Точный auth test driver опубликован как data artifact, без реальных ключей и
без access tokens; это существующая local synthetic fixture, не новый account.
Каждый fake-LIVE процесс имеет собственный DISPOSABLE journal и dummy key;
никакой actual evaluation journal не монтируется. Это независимые тестовые
fixtures, не сброс или копия настоящего journal52.

## Provenance и состояние

[Финальный пакет](pr404-recovery-final-20261103-evidence/README.md) содержит
source/backend/frontend image IDs, compiled build-info, instance/transport/network,
точные driver hashes и artifact SHA256. CI публикует текущий checkout SHA вместе
с результатом runtime projection/hash verification. CI не объявляет local Docker
Desktop запуск собственным remote E2E.

Стек возвращён к совпадающим fixture frontend/backend; backend только на internal
network, LIVE mounts/egress отсутствуют. Реальный journal остаётся52 attempts,
575120 microUSD reserved. Новых provider calls, реальных данных, production,
платежей, уведомлений или больших benchmarks не было. Все коммиты добавлены в
тот же PR404 вместе с предшествующей работой, без merge/deploy.

Прежний настоящий LIVE failure остаётся FAIL; новые MockTransport tests его не
исправляют задним числом. Настоящий external cap, независимый custodian trust pin,
signed admission и network-level egress review всё ещё нужны до нового paid run.
Real-user outbound/privacy и остальные pilot gates остаются BLOCKED/OPEN.

CI note: первый финальный frontend job прошёл63 основных browser contracts,
7 pairing/recovery и build matrix, но provenance не нашёл ancestor source из-за
shallow checkout. Frontend job теперь получает fetch-depth0; проверка исходного
runtime сохранена, не заменена слабой проверкой только текущего HEAD.

Mobile CI дополнительно обнаружил, что общий production-like runner автоматически
подхватил lab-only файл без соответствующего build mode. Он исключён из общего
test discovery и остаётся обязательным в отдельном AI frontend job с
playwright.ai-lab.config.ts. Проверка --list подтверждает разделение; assertions
не ослаблялись. Runtime inputs не менялись.

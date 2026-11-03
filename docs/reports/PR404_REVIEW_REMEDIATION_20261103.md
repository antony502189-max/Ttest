# Исправления полного review PR #404

3 ноября 2026, Europe/Moscow. Review пользователя
`Ttest_PR404_full_review_2026-11-03.md` относится к HEAD `7ef3d34`; проверен
по текущей ветке с последующими LIVE-failure исправлениями, не принят как
инструкция на новые paid calls или production. Все изменения находятся в той же
ветке/PR #404 вместе с прежней работой. Исторические evidence не перезаписаны.

## Результат по замечаниям

| ID | Исправление | Проверка |
| --- | --- | --- |
| PR404-01 P1 | Offline runner проверяет живую backend attestation, фактический source/transport и Docker internal network/отсутствие LIVE mounts до сессий/query. Нулевой outbound выводится из проверенного MockTransport+изоляции, до проверки report оставляет null. | Реальный старый fixture frontend + fake LIVE-factory: runner отказал до query, fake journal остался51, UI writes0; ASGI/Playwright отрицательные тесты. |
| PR404-02 P1 | Lab middleware связывает каждый AI request с parser/source/server instance; mismatch отказывает до session/quota/parser. Frontend повторно attests перед каждым AI request, а capabilities при непарном клиенте скрывают AI. Статический build-info больше не является допуском. | Оба смешанных frontend/backend сочетания дают409/нет AI entry; matching fixture15/15; matching LIVE-factory+fake provider3/3. |
| PR404-03 P1 | Внешний подписанный origin proof связывает canonical host/runtime path/device/inode и journal ID. Identity перепроверяется при каждом SQLite connect; original journal ID фиксируется в той же БД. Host preflight проверяет настоящие Docker image IDs. | Копия, подмена того же пути, смена journal ID, другой image и неучтённая история отвергаются. Реальный файл52 не копировался/не модифицировался. |
| PR404-04 P2 | В SAME SQLite под BEGIN IMMEDIATE сохраняется UNIQUE(journal_id,case_id)→attempt_id; reservation и consumed-case атомарны. Нельзя занять3 места одним case или вернуть место после failure/cancel/unknown ACK. |6 конкурирующих sessions с ru-balcony + оба других case дают ровно3 HTTP mock attempts, один на case; thread race и failure matrix. |
| PR404-05 P2 | CI запускает backend boundary matrix, Playwright pairing и настоящую Vite build matrix; есть отдельная fake-LIVE factory без ключа и сети. |88 targeted tests,5 pairing browser tests,3 real builds+2 invalid builds; реальная local Docker/HTTPS/PG/Redis packaging matrix. |
| PR404-06 P2 | Public approval string остаётся только accidental-activation guard. Реальный entry требует Ed25519 signature внешнего custodian, pin его public key вне repo, source/images, expiry≤1h, физический journal proof, cases/budget и external-cap evidence hash. Production signer/реальный admission не создавались. | Подмена подписи/pin/SHA, expiry, отсутствие cap evidence, unreconciled baseline и старый token отвергаются до key/IO. Независимый provider cap остаётся операционным release blocker, а не выдуманным фактом. |
| PR404-07 P3 | Offline fixture map отделён в cached Python module; нет вызова LIVE smoke_cases/checksum и чтения corpus на каждом completion. Возвращается deepcopy. | При отказе/смене LIVE loader unrelated fixtures продолжают работать; отдельный тест соответствия3 fixture cases corpus. |
| PR404-08 P3 | Vite вычисляет lab mode только внутри ai-synthetic-lab, нормализует production lab env в пустую строку, проверяет whitelist mode и source SHA. UI использует эти compiled defines. | Production с inherited LIVE env не имеет lab notice/compiled lab flag; fixture/LIVE builds различаются; invalid mode/source отвергнуты. |
| PR404-09 P3 | Новый immutable runtime и отдельная provenance matrix: Git source, backend/frontend image IDs, compiled build-info, networks, driver hashes, hashes artifacts и runtime-input projection. CI связывает текущий checkout с проверенным runtime без ложного утверждения, что CI повторил локальный Docker stack. | CI verifier сверяет exact Git trees/blobs и artifact bytes, формирует единый ai-lab-ci-provenance.json и загружает evidence в browser artifact. |

## Проверки и границы evidence

Финальный функциональный runtime — **2f442dc75188b3d7f7362aea087fd5ab7d7fdaf3**,
собран из clean git archive. Backend/frontend source и реальные image IDs,
compiled mode, SHA driver и source tar записаны в
[provenance](pr404-remediation-20261103-evidence/provenance.json).
Финальный documentation/CI-artifact HEAD может быть потомком этого source;
CI доказывает равенство именно runtime inputs, а не переносит результаты с
отличающегося backend/frontend. Если runtime code поменяется, проверка падает.
Ранний прогон source53b077 также сохранён, явно отдельно от финального.

| Набор | Результат |
| --- | --- |
| Полный backend unit (app/tests не менялись) |1683 passed /16 skipped /397 deselected |
| Provider/lab/boundary regressions |88 passed /8 subtests |
| Существующие HomeAI browser contracts |56 passed |
| Новый Playwright frontend/backend mismatch |5 passed |
| Actual Vite builds / invalid config rejections |3 /2 PASS |
| Настоящий fixture UI/HTTPS/backend/PG/Redis recovery |15/15 PASS |
| Настоящая closed factory/PG/Redis с mock completion |3/3 PASS |
| Реальная Docker/HTTPS packaging matrix |оба mismatch blocked; fake-LIVE3/3 PASS |
| Mypy / Ruff / TypeScript / i18n |172 files success /PASS /PASS /PASS |

Наборы пересекаются, их не суммировать. Код выполнялся в local synthetic lab;
negative/positive LIVE composition использовала **обязательный MockTransport**,
DISPOSABLE journal и dummy key. Это не новый DeepSeek LIVE PASS. Сам повторный
запуск offline runner против fake-LIVE backend должен завершиться FAIL — именно
это проверяет guard; raw report не маскируется как успешный функциональный тест.
Старые неуспешные локальные test outputs сохранены в output, финальные raw
результаты/хэши добавлены отдельно.

Проверено, что обычный app.main остаётся disabled: capabilities=false, AI query503,
ordinary search200 с13 synthetic items. Lab вернулся к matching fixture
frontend/backend на internal network; реальные key/budget/admission mounts и LIVE
egress отсутствуют. Реальный evaluation journal остаётся52/$0.575120 без новых
attempts. Дополнительных paid calls, provider keys, real data/crawl/backfill,
production DB/deploy/public AI и большого capacity benchmark в исправлениях нет.

## Что эти исправления не утверждают

Подписанный допуск — операционная граница против случайных неверных запусков,
не sandbox против администратора с правом менять image, trust roots и mounts.
Signed hash утверждения об external cap не проверяет состояние provider account.
Настоящий независимый spending cap, custodian public key и signed release для
нового source не предоставлены — поэтому real LIVE startup теперь BLOCKED.
Host/network-level egress allowlist остаётся отдельным условием release; external
Docker bridge не объявляется таким allowlist.

Предыдущая настоящая provider attempt закончилась LLM_FAILURE и не получает
ретроспективный PASS. Real-user outbound BLOCKED до privacy/account/minimization
review, актуальный реальный каталог требует нового разрешения. Production-sized
migration rehearsal OPEN, capacity ISSUE-004 OPEN/BLOCKED/SLO FAIL и stage3
пропущен владельцем. Эти продуктовые gates не закрываются fake-transport тестами.

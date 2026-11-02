# Закрытая UI-композиция intent adapter

Дата: 1 ноября 2026. PR [#403](https://github.com/antony502189-max/Ttest/pull/403),
ветка `codex/post-merge-remediation`, existing main-integration-audit checkout.
Runtime **b77423bc8b52eece184f7430d5894be61528e2e3**, `https://localhost:9443`.
Режим **decision-transport-fixture**, API mocks=false, external provider calls=0.
Итоговые изменения после runtime касаются drivers/docs/evidence; hashes входов
runtime сохранены в [attestation](ai-parser-ui-evidence/attestation.json).

## Реализованный путь

`UI → HTTPS /ai-search/query → quota/reservation → shared DecisionDeepSeekIntent
→ model transport → strict IntentDecision → server-owned IntentPatch → current
typed intent → verified SQL cards/map → CAS/receipt/debit → exact retry/recovery`.

`IntentDecision`, prompt и decode вынесены из `ClosedDeepSeekIntent` в общий
adapter. Закрытый HTTPS eval наследует тот же код и сохраняет отдельный metered
transport, approved corpus gate и прежний durable budget. Из UI runtime можно
проверить настоящий provider JSON protocol, не подменяя HTTP AI endpoint, SQL,
receipt или ownership. Модель не назначает session/version/identity, не пишет SQL.
Валидация duplicate JSON keys, refusal/truncation, extra fields, merged-state
consistency и semantic no-op остаётся прежней; 88 transport/eval тестов прошли.

Новый lab mode задаётся только явным launcher parameter. В нём transport выдаёт
synthetic completion bytes и fault injection; затем реальный adapter декодирует
их как provider ответ. Конечный fixture vocabulary не понимает произвольный язык
и не является model-quality доказательством. UI предупреждает о simulated data/
responses и запрещает ввод личных данных, без ключей или технических секретов.

`finite` по умолчанию сохраняет прежний конечный SyntheticParser и старые drivers.
Оба режима живут в прежних owned containers/volumes. Backend network проверяется
как internal до мутаций launcher; backend не подключён к edge network. Реальные
credentials запрещены `require_lab`, неизвестный parser mode отвергается.
Обычный `app.main` не создаёт runtime. Нет production/public activation switch.

UI policy для adapter: total10s, HTTP timeout8s, max_attempts1, max_tokens1024,
response≤65536bytes; execution15s/HTTP20s сохраняются. Эти пределы принадлежат
offline composition и не меняют 25s/2-attempt policy отдельного LIVE eval.
Перенос live eval в UI требует отдельной reviewed композиции и бюджета,
согласованных с execution deadline; прямое подключение его 25s parser guard отвергает.

## Сквозной результат

[13 сценариев PASS](ai-parser-ui-evidence/acceptance.json) в настоящем Chrome,
HTTPS frontend/backend, PostGIS и Redis, viewport390px:

- UI ввод трёх последовательных запросов, server-owned version, hard pets/budget
  сохранены при soft balcony, настоящие cards/map с одинаковым intent hash.
- Guest quota3, exact success replay с прежним receipt, изменённый payload с тем
  же key отвергается. Reload возвращает owned cards. Raw phrases отсутствуют в
  localStorage/sessionStorage.
- Настоящий UI login; guest session не доступна auth identity. Clarification,
  no_change и unsupported показаны в UI фиксированными сообщениями: version0
  сохраняется, debit0, exact retry не вызывает transport повторно.
- Model boundary invalid completion, cancellation и timeout дают terminal
  zero-debit outcome; reserved0. Timeout adapter10s завершается до execution15s.
- Потеря ACK после настоящего SQL commit: HTTP503, затем прежний succeeded
  receipt, одно списание и один transport attempt. Stale version отклоняется.
- Browser disconnect удаляет ответ только после настоящего commit; UI сохраняет
  точный payload/key в памяти и восстанавливает receipt. «Перестать ждать» во
  время transport не объявляет rollback: exact retry возвращает durable outcome.
- Настоящие metrics не содержат проверенные raw phrases, session IDs и bearer.

Скриншоты: [guest cards](ai-parser-ui-evidence/guest-cards.png),
[auth recovery](ai-parser-ui-evidence/auth-recovery.png).

Первый прогон нашёл реальный дефект: dependency `CancelledError` выходил из
private route, вызывая общий500/traceback. Теперь при отсутствии actual task
cancellation возвращается fixed503/no-store; настоящая отмена HTTP task
продолжает распространяться. Два regression tests проверяют обе ветви и отсутствие
private canary в логах. При первом повторе исправлялся также driver: после HTTP
изменения версии он должен reload/refresh UI, а не продолжать с устаревшей версией.
Локальные неуспешные artifacts сохранены, успешный итог записан отдельно.

## Проверки

| Набор | Результат |
| --- | --- |
| Полный backend unit после cancellation fix |1675 passed /16 skipped /1041 deselected integration/PG |
| Real isolated PG execution/DeepSeek + Redis operating gates |90 passed |
| Lab assembly/default-disabled/finite/shared adapter |6 passed |
| HTTP cancellation/privacy targeted |35 passed (пересекаются с unit) |
| Mypy |171 files, success |
| Ruff app/tests и изменённых lab файлов |PASS |
| TypeScript/Vite immutable runtime build; driver syntax; diff check |PASS |

Числа не суммировать. [Validation record](ai-parser-ui-evidence/validation.json).
CI проверяется отдельно для точного опубликованного HEAD в PR; этот локальный
отчёт не объявляет pending workflows успешными. Capacity/SLO не измерялись.

## Повтор и release gates

Из чистого committed checkout, с Docker Desktop bin в PATH:

```powershell
./scripts/ai-text-lab.ps1 start -Parser decision-transport-fixture
node scripts/ai-text-lab-control.mjs seed
$env:PLAYWRIGHT_EXECUTABLE_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
node scripts/accept-ai-parser-ui.mjs
```

Driver использует существующий synthetic acceptance account; не сбрасывает квоту,
issuance buckets или eval journal. Частые повторы могут получить429: дождаться
технического окна, не обходить лимиты. Перед повтором сохранять существующие
`output/ai-parser-ui/` artifacts. Старый release driver запускать в `-Parser finite`.

[Provider privacy/outbound review](../ai-search-developer/DEEPSEEK_OUTBOUND_POLICY_RU.md)
содержит актуальные официальные ссылки и account-specific неизвестное.
Исполняемый real-user gate отклоняет любой текст до provider payload/IO; JSON
review не даёт activation. Regex не выдаётся за минимизацию. Account training
exclusion, region, retention/deletion SLA, contract/DPA и ответственный не подтверждены.
Нет разрешения ни на arbitrary user text, ни на новый платный live smoke.
Старый LIVE corpus24/24 и journal51/56/$0.564060 — прежние данные, не новый замер;
ключи и journal в этой работе не читались и не изменялись.

Закрытая UI/adapter composition проверена на synthetic model boundary. LIVE UI,
real-user policy/минимизация, production infrastructure и capacity ISSUE-004
остаются gates. Merge403/main/production/public activation, новые real data,
payments/notifications/Pages не выполнялись. Voice/ASR и delivery — отдельный этап8.

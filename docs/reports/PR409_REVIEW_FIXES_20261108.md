# PR409 review fixes — S2.2,08.11.2026

PR409-001: stale и capacity теперь завершают dispatched claim через прежний
lease/token guard в той же транзакции. Source/projection/success receipt не
меняются, reserve не возвращается. Новый явный retry немедленно получает новый
token и платит новую synthetic reservation в прежнем общем cap.

4 новых actual PG cases: stale/capacity × немедленный caller/lock waiter;
сравнение source/receipt/rematch state, finished status, token смена, used≤cap.
Первый тестовый запуск имел ошибку порядка аргументов нового теста; исправлен,
не считается зелёным. Final PG/process run фиксируется отдельно.
55 focused unit PASS, Ruff/mypy PASS. Полный CI нового head ещё нужен.

R-409-A: finished — завершение одной попытки, а не запрет явного retry. Автоматический
scheduler/retry daemon отсутствует. Standing real refresh требует отдельного scope.
R-409-B: terminal status assertions и waiter cases теперь явные.

| Outcome | Claim | Повтор |
| --- | --- | --- |
| refreshed / failed / stale / capacity после dispatch | finished, guarded commit | новый token/charge; success receipt предотвращает повтор effect |
| lease_lost | чужой/истёкший fence не завершается | после lease по прежнему контракту |
| in_progress / request_capacity / already_fresh | новая reservation не создаётся | нет refund/reset |

Это synthetic/mock бюджет, не provider USD journal. Нет real source/LLM calls,
ACK, merge или production deployment. Совместимость с410 проверяется отдельным
фактическим combined tree, исходные зелёные CI её не доказывают.

## Final source validation

Source `f799dbbc`: actual Linux PostGIS **16 PASS/0skip** (13claims,3hard process), в том числе4 новых terminal/waiter cases. 55 focused unit PASS. Наборы не суммировать как полный backend suite. Первый ошибочный test argument-order run не принят. Raw JUnit/hash рядом в pr409-review-20261108-evidence. Exact-head CI после push отдельный.

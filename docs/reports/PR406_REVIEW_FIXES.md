# PR #406 — полное ревью и исправления S2.2, 04.11.2026

Ревью охватывает весь diff PR от main `20435c2e36cabac5608780fe01ab75e47efe152c`: process harness, unit/PG tests, integration с existing coordinator/supervisor/leases/fences, документацию, runtime manifest и evidence-byte policy. Исходный PR head `17d2857f03ef1b303d46918f6d1d2cc9632e160f` прошёл11/11workflows SUCCESS; это не доказательство корректности найденных ниже edge cases и не CI исправленного source. Все шесть findings исправлены в **`61c4e027e3438ba1c4448cec88a24532677d920c`**. Независимые subagents не использовались; это self-review с воспроизведением и регрессиями.

| ID | Подтверждённая проблема | Исправление и проверка |
| --- | --- | --- |
| F-01 | `SystemExit(0)` до `run_once` выдавал outcome=committed без tick/receipt | One-way private pipe передаёт explicit status только после run_once и event-loop shutdown; exit0 без status=failed. RED→GREEN на настоящем child |
| F-02 | Полный deadline начинал отсчёт после `Process.start`, startup добавлялся сверху | Monotonic deadline до process setup, join получает только остаток. Startup-overrun test задерживает настоящий start и проверяет нулевой остаток и остановку child |
| F-03 | При failed reap повторный finally снова выполнял kill/join с полным reap budget | Одна cleanup path и одно bounded ожидание; unreapable-process fault проверяет ровно один kill и один reap join, fail closed без success |
| F-04 | Arbitrary pickle reducers args/factory исполнялись в controlling parent до child kill boundary | До spawn разрешены только фактически зарегистрированная module-level plain function и максимум16 exact scalar args с type/size bounds. Custom objects/callables, lambda/nested functions, non-finite floats/oversized config отклоняются без запуска reducer. RED marker test и negative input cases |
| F-05 | Parent start/join exceptions раскрывали исходный текст, включая private configuration | Parent IPC setup/start/join errors дают redacted SYNTHETIC_PROCESS_UNAVAILABLE; cleanup errors — SYNTHETIC_CHILD_REAP_FAILED. Injected private start error проверяет сообщение, suppress cause и закрытие handles |
| F-06 | PG process fixture имела constant catalog digest и принимала тот же journal с другой schema | Binding теперь содержит hash фактической unique schema и файла fixture bundle; повтор с другой schema отвергнут до DB I/O. Отдельный RED→GREEN test; actual kill/recovery suite также проверяет ровно2pending/completed rematch events |

## Итоговая проверка исправленного source

- **1729 backend unit PASS / 16skip**,1092integration deselected. Новый process unit suite входит в этот whole-tree прогон.
- **82 coordinator/supervisor/PG PASS**, включая настоящие kill в sync builder после PG claim, после PG publication/proof и после SQLite receipt. Recovery проверяет receipt/checkpoint/pending refresh, lease-before-expiry deferred, PG attempt/fence, stale-owner rejection и отсутствие повторной публикации.
- **116lab PASS / 1skip,8subtests PASS**. Пересекается с supervisor частью82, counts не суммируются.
- Ruff `app tests lab` PASS; mypy `app lab/ai_fact_process.py` —174source files PASS.
- Runtime manifest943inputs обновлён; provenance PASS, historicalEvidenceAppliesToCurrentRuntime=false. Production package finder по-прежнему включает только app*, references к process harness из app/startup/deploy/scripts/workflows отсутствуют; CI собирает tests по существующим directory scopes.

Raw XML, source caveats и SHA-256: [evidence](pr406-review-fixes-evidence/validation.json). RED reproductions содержат5failures и отдельный schema-binding failure. Промежуточный full unit run1728PASS/1FAIL/16skip выявил lambda validation; после исправления принят повтор1729PASS/16skip. Промежуточный process-unit run11PASS/1FAIL выявил Windows BrokenPipe на poll после clean exit; poll/recv теперь защищены общей EOF/OSError обработкой. Ранний16targeted PASS относится к промежуточному source и не заменяет финальные82/1729. Исторические raw artifacts не переписаны.

Runtime: existing Python3.12.14/pytest9.1.1 release-venv, Windows spawn. Новый owned `ttest-pr406-review-pg`, loopback55440/`ai_facts_test_review406`, PostGIS image `sha256:44126d872ac91993766c341e369c539e8196614321765d36a6f1bab0419a5fa5`; container и его anonymous volume удалены после тестов. Redis, существующие application/closed-lab containers/БД и настоящий budget journal не использовались. Existing CI использует Linux/Python3.13; его results рассматриваются только по точному новому head.

## Проверенные границы и оставшиеся gates

Это synchronous one-child API для trusted synthetic factories, а не OS service или sandbox. Cancel coroutine, ожидающей `asyncio.to_thread`, не прерывает сам thread; thread продолжает контролировать child до deadline. OS process creation нельзя прервать из того же thread; arbitrary custom serialization теперь исключена, startup time вычитается из ожидания после возврата OS call. SIGKILL/TerminateProcess controlling parent и descendants требуют внешнего OS supervision и не сертифицированы. Reap failure явно блокирует success; он не выдаётся за доказанное отсутствие child.

SQLite clock и PG lease expiry ускорены только в owned synthetic fixture; natural production timing не заявлен. `committed` pipe status не заменяет durable receipt inspection и не разрешает blind replay unknown commit outcome. На диске остаются существующие fences/claims/receipts; wrapper не совершает compensating mutations от имени погибшего owner.

Проверены совместимость source-filtered jobs, bounded cursor replay, exact receipt ACK/pending signals, source TTL/presence split и независимость обычного app startup. Новых startup/importer/scheduler/capability hooks, provider calls, ingestion, user outbound, real budget changes, large benchmarks или production activation нет. A3/A11 остаются partial; voice/saved/delivery и S3–S7 обязательны. Следующий шаг в едином плане — exact-head CI исправлений; затем S2 source-specific refresh chain. Merge/deploy этим ревью не выполнены.

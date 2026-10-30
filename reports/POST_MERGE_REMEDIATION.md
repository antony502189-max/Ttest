# Исправления замечаний post-merge аудита

Дата: 30 октября 2026, Europe/Moscow.
Код исправлений: `23ccd0b76ee383389811983426dd415085b9d7ac`, ветка
`codex/post-merge-remediation`. База аудита: `7d4c125574927181511c5f1bc7e201e20a8840a8`.

Исходный [отчёт аудита](MAIN_POST_MERGE_INTEGRATION_AUDIT.md) сохранён как
историческая запись. Его FAIL относится к проверенному старому main.

| Замечание | Изменение | Проверка | Статус |
|---|---|---|---|
| ISSUE-001, P1 | Общий `start-fullstack-audit.sh` применяет test-only geocoder override при старте backend и seed в обоих PR/main runners | Исполнение launcher с fake Docker/curl, проверка настоящего Compose config и реальные frontend/API/PostGIS tests: 23 passed, 7 skipped | Исправлено в ветке; remote CI требуется до merge |
| ISSUE-002, P2 | Единый синхронный `commitMapRoute`; camera idle не возвращает drawing mode и не пишет camera params после выхода в List/Filters | Старое управляемое reproduction теперь проходит; 10 повторных race checks и 65 map/navigation tests passed | Исправлено |
| ISSUE-003, P2 | Оба AI workflow слушают каждый main push; manual release дополнительно проверяет последние push runs точного main SHA по workflow path/event/branch/status | 24 CI/release/home regression checks passed; негативные stale/missing/failed/queued/cancelled/skipped варианты отклонены | Исправлено в коде; первые реальные main-push runs появятся после merge |
| ISSUE-004, P2 | Добавлен read-only `check-ai-map-capacity.py`, который пересчитывает raw evidence и требует measured SHA + полный протокол + успешный SLO | 6 capacity acceptance tests passed; поддельный cached summary, старый SHA, недостающий масштаб и raw failure отклонены; CLI без evidence возвращает1 | **Не закрыто: нужны отдельно разрешённые новые representative замеры** |
| ISSUE-005, P3 | Optional Pages configure/upload/deploy выполняются только при `PAGES_PREVIEW_ENABLED=true`; build/lint/typecheck остаются обязательными, disabled state явно отражён в summary | YAML/условия проверены regression tests; при opt-in настоящие 404/permission errors не подавляются | Исправлено на уровне workflow; Pages site/settings не включались |

## Исполненные проверки

Среда: native Linux snapshot в отдельном test container, Python3.13.14 с pinned
constraints, PostgreSQL16/PostGIS3.4, отдельные Redis и synthetic DB. Frontend
static checks также выполнены на Windows/Node24; Docker production build использует
прикреплённый к Dockerfile Node22. Ни одна application/staging/production DB не использована.

| Команда / suite | Результат |
|---|---|
| `ruff check app tests` + новые Python CLI | PASS |
| `mypy app` | PASS, 153 source files |
| `pytest -q -m 'not integration'` | **1564 passed, 31 skipped** |
| Новые capacity/CI contracts, финальный повтор | **21 passed**; входят также в unit suite |
| CI/release/home focused suite | **24 passed**; пересекается с unit suite |
| Map race tests + исходное audit reproduction, repeat2 | **10 passed** |
| APK/navigation/history/mobile map/Maps acceptance | **65 passed** |
| `playwright.ai-search.config.ts` | **50 passed** |
| `playwright.search-lifecycle.config.ts` | **62 passed** |
| `playwright.fullstack.config.ts` | **23 passed, 7 skipped**, actual API/PostGIS |
| Fresh database migrations для full-stack | PASS, полный upgrade head |
| `npm run lint`, `typecheck`, `build`, `test:security`, `test:bundle-security` | PASS |
| Supply-chain и immutable migration compatibility | PASS |
| Compose full-stack harness contract | PASS |

31 unit skips — 28 Windows/PowerShell cases и три opt-in public-source/research
tests. PowerShell launcher/monitor не изменялись; их 28 Windows cases были отдельно
проверены в исходном аудите. Full-stack skips — прежние conditional/legacy cases.
Полный PG regression на931 cases и historical upgrade matrix повторно не запускались:
backend application SQL/models/migrations не менялись; их исходные результаты
сохранены в audit report. Здесь отдельно создана новая full-stack DB и пройден
реальный полный migration path.

Локальные raw logs/JUnit: `output/post-merge-remediation/` managed worktree.
Компактная матрица: `reports/post-merge-remediation-evidence/test-results.json`.
Пересекающиеся проверки не объявляются дополнительными уникальными tests.

## Оставшаяся граница

План capacity-прогона и необходимые ресурсы записаны в
[docs/post-merge-remediation.md](../docs/post-merge-remediation.md).
30 октября 2026 владелец отдельно разрешил указанный изолированный прогон.
Ресурсы и namespace готовятся по этому плану; до получения raw evidence
100k/500k/1m результат не объявляется успешным, p95/p99 не выдумываются и
ISSUE-004 не закрывается. Окончательный capacity report будет отдельным artifact.

Public AI/ASR/providers, notifications, GitHub Pages site, deployment configuration
на сервере и production rollout не активировались. Ветка не merged. До выпуска
нужны review, green PR checks и новые green exact-main push checks после merge.

# PR401: устранение замечаний comprehensive review

## Повторное полное ревью: PR401-R01–R08 (29 октября 2026)

Исправления по PR_401_FULL_CODE_REVIEW_2026-10-29.md:

| ID | Исправление | Регрессия |
|---|---|---|
| R01 | Полная нагрузка требует 200 попыток и фактического перекрытия 50/100/200 клиентских операций по raw timestamps. Малые пробы не завершают протокол; early stop допустим только после полной неуспешной первой волны | 1/49/99/199, последовательные операции, полная матрица и ранний отказ |
| R02 | До timed SQL одна read-only repeatable-read транзакция сверяет все девять таблиц, r01_entities, provider count, template/dataset/meta, профиль и триггер | Подмена каждого счётчика и профиля; маленькие реальные PostgreSQL-таблицы |
| R03 | Отдельный каталог и immutable experiment.json: commit, archive hash, image IDs, DB container, seed/profile. Идентичность хранится в БД; raw-файлы ссылаются на завершённые уникальные phase manifests | Смешение dataset/load/cancellation/template/manifest/revision, отсутствующий manifest, изменение experiment |
| R04 | Двадцать контролируемых SQL с серверным барьером активности; подсчёт принятых и подтверждённых отмен, ранних завершений и ошибок, проверка освобождения и повторной работы пула | Ноль реальных отмен не проходит; настоящий PostgreSQL подтверждает 20 отмен |
| R05 | Точная сеть, единственное подключение, alias, pinned DB image, running container ID; read-only identity check до миграций и повторно в Python | Fake Docker: неверные network/network ID/alias/image/database |
| R06 | Каждая строка мониторинга связана с experiment/run/monitor/DB. Для каждого сценария проверяются отдельная пара start/stop, временное покрытие, samples до/после, отсутствие gaps/errors | Старые run/revision, другой DB, неверный интервал, gaps, непарный lifecycle |
| R07 | Сводка пересчитывает агрегаты и pass по raw attempts. Противоречия дают INCONSISTENT, незавершённый масштаб и ненулевой CLI exit code | Подмена p99/pass/failures/p50; сырые метрики сохраняют приоритет |
| R08 | --sources разрешён только для initialize; seed/measure используют проверенный immutable profile | Ранний отказ CLI для seed/measure --sources |

Исторические raw-файлы не изменены. Новая строгая сводка не подтверждает их
provenance/cancellation задним числом; прежние заявления о completed scales ниже
относятся к предыдущей версии инструмента. Новых больших прогонов и данных
post-fix p95/p99 нет. Публичная активация остаётся заблокированной прежними gates.

Локальная проверка текущих исправлений: 1528 backend unit passed, 15 ожидаемых
skips; 53 PostgreSQL passed (14 проверок toolchain и 39 proof-регрессий).
Ruff для app/tests и обоих Python-скриптов, mypy для 153 app-файлов,
Bandit с порогом medium/high, pip-audit точного constraints-графа и проверка
supply-chain pins прошли. PowerShell fake-Docker сценарии исполнялись на Windows.
Эти числа пересекаются с целевым unit-набором; они не суммируются как независимые.
Небольшой PostgreSQL-контейнер использовался только для синтетических регрессий.

## Предыдущий этап исправлений (историческая запись)

29 октября2026. Проверены замечания к HEAD `0af4e1a4` из пользовательских
PR_401_COMPREHENSIVE_REVIEW.md и PR_401_FIX_PLAN.md. Все пять находок подтверждены
в диагностических инструментах; application SQL, API, UI, миграции, зависимости
и activation gates относительно этого HEAD не изменялись.

| ID | Исправление | Проверка без нагрузки |
|---|---|---|
| PR401-001 | Git errors и dirty checkout отклоняются до Docker; запускается отдельный read-only git archive snapshot, его SHA-256 и происхождение записываются в metadata | Clean/staged/unstaged/untracked/git-failure; содержимое snapshot и hash; правка checkout после экспорта не меняет snapshot |
| PR401-002 | Source/observation counts и текст baseline/fanout берутся из dataset; старый формат распознаётся только по точному отношению counts | 2-source→200000, 10-source→1000000; некорректные counts отклоняются; исторические raw метрики совпали |
| PR401-003 | Python и PowerShell проверяют границы total/samples/candidate и комбинации phase/options до инфраструктуры; пустой sample set явно отвергается | Нулевые/отрицательные/выходящие за лимиты числа, candidate вне bounds, неверная фаза; samples1/50/200 допустимы |
| PR401-004 | Monitor проверяет профиль container/output; пишет sanitized failures, валидирует stats JSON и завершает работу после последовательных ошибок | Fake Docker: exit error, malformed/empty/missing fields, profile mismatch, recovery, success и stop marker; ресурсные gaps видны в summary |
| PR401-005 | Completion выводится из load matrix, sample counts и cancellation/pool reuse; stop-marker сравнивается с файлами | Остановка до/после100k/500k, отсутствующий/частичный load, пустые samples, отсутствующий/неуспешный cancel, противоречивый marker |

Regression suite: backend/tests/test_ai_map_toolchain.py и
backend/tests/test_ai_map_benchmark_safety.py. PowerShell-тесты запускают настоящие
скрипты с функцией fake Docker в отдельном процессе и временным маленьким Git
репозиторием. Реальный Docker, migrations, seed и benchmark в этих тестах не
запускаются. Если PowerShell недоступен, эти случаи явно skipped; Python-тесты
работают независимо от ОС.

До исправлений сохранены провалы новых regression cases для всех пяти групп.
Полный локальный backend unit suite после изменений:1470 passed,15 expected
skips; Ruff и mypy153 passed. Для окончательного коммита требуется свежий CI;
результат отражается в описании PR и итоговом пользовательском отчёте.

На сохранённом архиве независимо повторены только offline calculations:
100k→18 сценариев/3600 ошибок,500k→18 сценариев/2100 ошибок. Load metrics
совпадают с прежними summary; новый отчёт различает завершение измерений и
прохождение SLO. Для legacy resource series без lifecycle markers полнота
обозначена unknown. Evidence ZIP и исходные исторические данные не изменены.

Большие100k/500k/1m прогоны, backfill, crawling, реальные providers/ASR, платные
API, публичная AI-активация, merge и deployment не выполнялись. Post-fix p95/p99
и production capacity не заявляются. [Протокол](MAP_CAPACITY_PROTOCOL.md) сохраняет
требование отдельного согласования любых новых больших измерений.

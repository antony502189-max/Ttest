# Ограниченный synthetic LIVE UI smoke: подготовка

3 ноября 2026, Europe/Moscow. **Пользователь разрешил smoke; LIVE результат FAIL.**
После исправления readable-but-unwritable journal выполнена1 новая provider
attempt: cumulative52, резерв575120 microUSD, usage новой попытки неизвестен.
Остановлено на `LLM_FAILURE`, следующие2 попытки не использованы. Стенд возвращён
в offline, key/budget mounts и egress удалены. [Фактический отчёт](../reports/AI_CLOSED_LIVE_UI_20261103.md).
Ниже сохранён исходный план, а не заявление о LIVE PASS или новом разрешении.
PR #403 уже слит; main `4a60e163` принят отдельно. Обычный `app.main`
сохраняет AI disabled. Новый код не разрешает real-user outbound.

## Конкретный предлагаемый запуск

Три отдельные owned guest sessions через `https://localhost:9443`, selector
режима аренды — «не задавать». По одному запросу на пустое `criteria`:

| Corpus case | Точная synthetic фраза | Ожидаемое условие |
| --- | --- | --- |
| ru-balcony | Обязательно с балконом. | balcony hard=true |
| es-monthly | Como máximo 600 euros al mes. | budget hard=600 EUR/monthly |
| en-negation | The apartment must be unfurnished. | furnished hard=false |

Это subset прежнего corpus24, digest
`7b722ab6caa0bf3377a0ace8fcddecf6daa7f7cb9bcebec515ab0cac9997d288`.
Текст и полное текущее typed criteria должны совпасть **до** сборки provider
payload/IO. Изменение corpus требует нового review. Gate не является общей
PII-минимизацией. Иные фразы, история диалога и объявления запрещены.

В provider уходят только fixed instructions/schema, synthetic text и criteria.
Нет session/subject/result IDs, cookies, истории, карточек, expected answers.
Shared strict decision adapter проверяет ответ; identity/version назначает сервер.

Ровно до **3 новых HTTP attempts**, без automatic retry. Policy: timeout8s,
parser deadline10s < execution15s < HTTP20s; max_tokens1024, bytes65536,
redirects/env proxy/streaming выключены. Это ограниченная функциональная
проверка, не performance или model-quality certification.

Только SAME `output/ai-intent-provider-v1/budget.sqlite3`, без копирования,
создания, переноса или сброса. Factory открывает SQLite с `mode=rw`, проверяет
binding и минимум прежних51 reservations/$0.564060. Атомарный `BEGIN IMMEDIATE`
останавливает этот smoke при cumulative54 attempts, в том числе после restart
и при конкурирующих процессах. Прежние global56/$0.75 не увеличены.
Локальный дополнительный резерв — **33180 microUSD ($0.033180)**; это allowance,
не прогноз счёта. Перед разрешением требуется заново проверить тарифы.
Failures/cancellation/lost ACK не возвращают reservation. Исчерпание — остановка.

После каждого успешного commit: сравнить typed criteria, cards/map intent hash,
сделать exact retry с тем же key и reload. Receipt должен сохраниться, provider
attempt и debit не должны повториться. При неопределённости сначала status GET;
не отправлять новую модельную операцию. Не добирать число успешных случаев
дополнительными вызовами при сбое.

## Подготовленный код и границы активации

- `backend/lab/closed_ui.py`: exact corpus gate, reopen-only cumulative budget,
  отдельная UI-compatible policy и factory на общей UI/backend composition.
- `backend/lab/closed_ui_entry.py`: явная Docker factory. Проверяет новый
  approval token и digest, затем существующую историю, затем читает dedicated
  key из единственного backend-only file mount. Import ничего не активирует.
- `deploy/ai-text-lab/closed-ui.override.yml`: не используется обычным launcher.
  Отдельный external egress network подключается только к backend; ключ не
  монтируется в frontend/maintenance. SAME budget **directory** монтируется rw,
  включая общие SQLite locking/journal files. Missing bind paths не создаются.
- `VITE_AI_CLOSED_LAB=closed-live-synthetic`: отдельная подпись UI о настоящей
  модели и simulated каталоге; offline UI продолжает говорить о simulated replies.
- Обычный `ai-text-lab.ps1` остаётся offline, не принимает live mode/ключи.
  Status tooling offline lab нельзя выдавать за статистику LIVE provider.

**Override запускался только для согласованного smoke и затем отключён.** Для нового прогона нужны review и отдельное согласование после failed outcome;
при первоначальной подготовке требовались отдельное новое разрешение
владельца на эти3 attempts и outbound, проверка exact source/build,
backend-only key mount, доступа к SAME journal и изоляции сети. Имена требуемых
параметров перечислены в override; значений ключа или реального journal в отчёте
нет. Новый approval token `deepseek-synthetic-ui-smoke-v1` отделён от старого eval;
знание token не означает пользовательского разрешения.

Egress transport допускает только POST HTTPS `api.deepseek.com/chat/completions`,
стандартную TLS verification и один connection. Отдельная Docker bridge сама
по себе не является сетевым allowlist/sandbox: это явно остаётся частью review
перед запуском, а не доказательством изоляции произвольного доверенного Python.
После smoke LIVE сеть и key/budget mounts удалены. Для запуска нужен immutable frontend
build с LIVE подписью, отдельная проверка конфигурации и возврат к offline
configuration после bounded smoke. Production/public activation сюда не входят.

## Разрешённое повторение без провайдера

Из backend, без сети, ключа и старого journal:

```powershell
python -m lab.closed_ui --output ../output/NEW-UNIQUE-plan.json
python -m pytest -q lab/test_closed_ui.py lab/test_ai_text.py lab/test_decision_parser.py tests/test_ai_closed_deepseek.py
```

CLI только формирует план и не перезаписывает evidence. После committed clean
HEAD обычный launcher собирает `decision-transport-fixture`. Затем:

```powershell
docker exec ttest-ai-text-lab-backend python -m lab.rehearse_closed_ui
node scripts/rehearse-ai-closed-ui.mjs
```

Первый прогон использует **новый disposable simulated journal** с51 искусственными
history rows и реальный `ClosedUIParser`/budget/HTTP/PG/Redis; подменён только
transport. Он не читает настоящий eval journal/ключ, не производит provider IO
и не является браузерной проверкой. Второй проверяет браузерные3 scenarios,
exact retry/reload и карты в прежнем offline mode; provider replies — fixtures,
не настоящий LLM. Evidence нового browser driver всегда сохраняется в UUID path.
Свежие browser contexts разделены паузами35s, соблюдая реальный guest issuance
limit2/min; часовые buckets и quotas не сбрасываются. При429 ждать технического
окна, а не обходить ограничение новым identity/IP.

## Короткий список до закрытого пилота

1. **LIVE UI synthetic smoke:** один provider attempt завершился failed,
   LIVE gate OPEN/FAIL. Нужны review диагностических изменений и отдельное
   согласование нового bounded прогона без сброса SAME journal52.
2. **Real-user outbound:** BLOCKED. Нужны account-specific owner/DPA,
   no-training, region/transfers, retention/deletion SLA, основание/уведомление
   и проверяемая минимизация с negative tests. Общая policy их не подтверждает.
3. **Реальный актуальный каталог:** новое разрешение и проверка coverage/freshness.
   Исторический Flatio pilot удалён; текущая лаборатория synthetic.
4. **Инфраструктура пилота и rollout:** закрытый доступ, мониторинг/восстановление,
   production-sized migration rehearsal. Маленькая rehearsal этого не заменяет.
5. **Capacity:** ISSUE-004 OPEN/BLOCKED, прежний SLO FAIL; пункт3 пропущен
   владельцем. Без нового поручения benchmark не запускать и gate не закрывать.

Voice/ASR и saved-search rematch/delivery остаются отдельным этапом8.

# Пункт 4: закрытая проверка настоящего intent provider

Дата: 1 ноября 2026, Europe/Moscow. Контракты provider сверены 31 октября.

**Статус: реализация и offline проверки; живой прогон НЕ выполнен.**
1 ноября владелец явно выбрал «Пока только offline, живые вызовы не разрешаю».
Это решение действует до нового явного разрешения; наличие команды Live ниже
описывает подготовленную возможность, а не разрешает её исполнять.
Пункт 3 пропущен по поручению владельца; ISSUE-004 OPEN / capacity BLOCKED.
Наличие transport и успешные mocks не являются измерением качества модели.

## Что готово

`ClosedDeepSeekIntent` реализует существующий `parse(text, current) -> IntentPatch`.
Единственная внешняя граница — `POST https://api.deepseek.com/chat/completions`.
HTTPX с CA/hostname verification, без env proxy, redirect и скрытых transport
retries. Отдельный CLI `lab.intent_eval` не запускает приложение или БД.
Обычный production runtime disabled; наличие ключа ничего не включает.
`OfflineDeepSeekIntent` по-прежнему принимает только `httpx.MockTransport`.
Синтетический UI lab остаётся offline и не принимает реальные credentials.

Модель возвращает строгий `IntentDecision`: patch / clarification / no_change /
unsupported. Последние три исхода не создают patch или поиск. Для patch сервер
добавляет session/version и применяет существующие merged-state/no-op guards.
Модель не управляет SQL, identity, quota, evidence или фактами объявлений.
Этот CLI проверяет только понимание; инъекция parser в UI/HTTP, представление
уточнений и общая продуктовая приёмка здесь ещё не сертифицированы.

## Предложенный первый живой прогон — требует согласования

- Provider: **DeepSeek**, model **`deepseek-flash`**, non-thinking JSON mode.
  Текущая официальная версия за alias: DeepSeek-V4.1-Flash-1017. Alias может
  измениться; результаты относятся к дате прогона, не ко всем будущим версиям.
- 24 синтетических примера: 8 RU, 8 EN, 7 ES и 1 ES/EN.
  [Полные тексты и эталоны](../../backend/lab/intent_cases.v1.json).
- SHA-256 corpus: `7b722ab6caa0bf3377a0ace8fcddecf6daa7f7cb9bcebec515ab0cac9997d288`.
- Исходящие данные: только текст одного примера, его текущие typed criteria и
  фиксированные системные инструкции/JSON Schema. Ни эталоны/labels, ни история,
  IDs, quota, SQL, каталог, URL, сведения пользователей или документы не уходят.
- Gate допускает только точные пары text/current из corpus. Это allowlist
  синтетики, а не универсальный PII-redactor. Реальные запросы не разрешены.
- Отдельный тестовый ключ/аккаунт; не использовать application credentials.
  У провайдера остаются обычные сетевые/account metadata. Не предполагается
  zero-retention или особый запрет обучения: такое соглашение не установлено.
  Согласование относится только к передаче этой синтетики на условиях аккаунта.
- Максимум **32 HTTP-попытки** на весь согласованный прогон, включая retry,
  ошибки, timeout и возобновления; максимум 2 попытки на пример, последовательно.
- Timeout 10 s, общий deadline 25 s на пример, backoff с jitter/Retry-After,
  не более 65 536 bytes ответа, max output 1024 tokens. Невалидный смысл/JSON,
  refusal/truncation не вызывают автоматического дополнительного запроса.
- Локальный бюджет резервов **$0.50**. Резерв каждой попытки: **$0.01106**;
  максимум 32 попытки резервирует $0.35392. Основа: peak/cache-miss $0.30 за
  миллион input tokens и $1.20 за миллион output, input allowance 32 768 tokens.
  UTF-8 admission estimate использует запас 2x и framing, но **это не гарантия
  токенизации или верхнего счёта провайдера**. Нужен отдельный ограниченно
  пополненный/ограниченный аккаунт; цены перед живым прогоном сверяются снова.
  Ответ `usage` проверяется; превышение allowance блокирует следующие вызовы.
- SQLite journal сохраняет полный резерв ДО IO и не возвращает его при
  неопределённом ответе. Нельзя удалять/менять journal или использовать новую
  папку ради нового лимита без отдельного согласования. Observed usage и
  peak cost estimate сохраняются отдельно от резерва; это не выписка billing.

## Критерии понимания

Проверяются hard/soft, отрицания и снятие условия, monthly/nightly/weekly,
неуказанный период и USD, pets/размер/снятие, состав party, неоднозначность,
конфликтующие даты/периоды/балкон, no-op, unrelated/injection и сохранение
посторонних условий при follow-up. Сравнивается **весь итоговый typed intent**,
а не только возвращённые поля. Порядок conjunction и формат денег нормализуются.

Для однозначных запросов требуется точное совпадение ожидаемых условий без
добавленных/потерянных ограничений. Для неоднозначных/конфликтующих ожидается
clarification, для неподдерживаемых — явно указанный допустимый отказ.
Транспортная ошибка никогда не считается правильным отказом по смыслу.
Отдельно видны typed patch count, semantic pass, группы/языки и latency.
Принятие первого набора — 24/24, без ложного принятия конфликтов/no-op.
Даже 24/24 — только результат небольшого согласованного набора, не доказательство
обобщения или качества всех пользовательских запросов. До результата эталоны
предложены к согласованию, а не объявлены утверждёнными.

## Запуск

Из существующего чистого checkout/ветки после commit. Docker Desktop и локальный
image `ttest-ai-fact-population-tools:20261031` с проверенным image ID обязательны.
Launcher архивирует exact HEAD, сверяет corpus, записывает source/image/archive
hashes, использует отдельный одноразовый контейнер без БД, host ports или deploy.

```powershell
./scripts/run-ai-intent-eval.ps1 -Action Prepare
```

Prepare работает с `--network none`, не читает ключ и сохраняет план, не оценку.
Результаты: `output/ai-intent-provider-v1/run-*/source.json` и `result.json`.

**Только после явного согласования** corpus, отправляемых данных и расходов:
создать в корне этого audit checkout игнорируемый Git файл
`.env.ai-intent-eval.local` с единственной строкой
`AI_INTENT_EVAL_DEEPSEEK_KEY=<отдельный тестовый ключ>`. Сам ключ не отправлять
в чат, не передавать аргументом shell, не выводить, не коммитить. Launcher
передаёт файл только через Docker `--env-file`; одноразовый контейнер удаляется.

```powershell
./scripts/run-ai-intent-eval.ps1 -Action Live `
  -Approval deepseek-synthetic-intent-v1 `
  -ApprovedCorpusSHA256 7b722ab6caa0bf3377a0ace8fcddecf6daa7f7cb9bcebec515ab0cac9997d288
```

Journal всегда `output/ai-intent-provider-v1/budget.sqlite3`; повторный запуск
сохраняет прежние резервы. Evidence не перезаписывается. В evidence только
case ID/category/language, фиксированный outcome, расхождения имён criteria,
timing и usage/cost counters — без provider bodies, текста запросов и секретов.
Завершение live CLI с ненулевым кодом при semantic fail — ожидаемая защита,
а не повод объявить валидный JSON успешным пониманием.

## Официальные контракты, сверены 31.10.2026

[Chat API](https://api-docs.deepseek.com/api/create-chat-completion/),
[JSON mode и пустой/обрезанный ответ](https://api-docs.deepseek.com/guides/json_mode/),
[модель и цены](https://api-docs.deepseek.com/quick_start/pricing/),
[usage и приблизительность token estimates](https://api-docs.deepseek.com/quick_start/token_usage/),
[ошибки](https://api-docs.deepseek.com/quick_start/error_codes/),
[общая privacy policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html).
Общая privacy policy не заменяет отдельное API/data-processing соглашение и
не является разрешением отправлять реальные пользовательские данные.

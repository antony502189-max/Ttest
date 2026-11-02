# DeepSeek: граница исходящих данных

Проверено 1 ноября 2026. Область — direct API `api.deepseek.com`, account,
использованный ранее для закрытого intent eval. Account settings, ключи и
переписка с provider не открывались. Это review record, не согласие на обработку.

## Первичные документы и предел подтверждения

[Open Platform Terms](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html),
release 22 апреля / effective 29 апреля 2026: §3.3 возлагает на разработчика
раскрытие обработки, основание и ответы на запросы субъектов; §5.5 отдельно
оговаривает данные конечных пользователей downstream приложения. Общая privacy
policy не устанавливает для них автоматически условия API account. §2.2 запрещает
раскрывать ключ клиентскому коду. Оператор platform указан как Hangzhou DeepSeek
Artificial Intelligence Co., Ltd. Отдельные account/DPA условия не подтверждены.

[Общая Privacy Policy](https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html),
Last Update 10 февраля 2026:
перечисляет обучение/улучшение среди целей и право opt-out; это не доказательство
действующего no-training для нашего API account. Указывает прямую обработку и
хранение в КНР. Retention зависит от цели/обязательств; фиксированный API TTL и
ZDR здесь не подтверждены. Предусмотрены обращения за удалением/реализацией прав
через privacy@deepseek.com; срок фактического удаления нашего API input, logs,
backup и training artifacts неизвестен. Не переносить эти общие положения на
end-user API как согласованный договор. Ранее сохранённый PDF не подменяет
актуальные platform terms.

## Review и техническая граница

Машиночитаемый [review](../../deploy/ai-text-lab/deepseek-outbound-review.json)
находится в `deploy/ai-text-lab/deepseek-outbound-review.json` (путь от repo root).
Проверка из backend:

```
python -m app.services.ai_provider_privacy ../deploy/ai-text-lab/deepseek-outbound-review.json
```

Валидный config означает BLOCKED, а не разрешение. Strict schema отвергает
activation=true, неизвестные поля и выдуманные подтверждения. `RealUserOutboundDenied`
отвергает любой input до сборки provider payload/IO. Нет production activation
flag, env key не регистрирует runtime. Произвольный текст не проходит regex
«очистку»: текущая доказуемая минимизация для real-user input — полное отсутствие
передачи. Guard не является process sandbox для произвольного доверенного Python.

Для подготовленного adapter envelope разрешены только `text` и текущие typed
`criteria`, плюс фиксированные schema/instructions/model limits. Цель — только
intent interpretation, без подбора объявлений или подтверждения их свойств.
Разрешение этих двух полей в будущем НЕ означает, что произвольное содержимое
text безопасно. Перед включением нужен проверяемый локальный этап минимизации
и его negative tests, включая скрытые контакты, биографии, health data и prompt
injection; одной инструкции пользователю недостаточно.

Запрещены history, user/subject/session/result IDs, cookies, browser IP, access
tokens, контакты, имя, платежи, документы, source HTML/URL, listings/evidence,
SQL, labels и expected answers. Provider неизбежно видит серверный egress IP,
время и выделенный bearer key на TLS boundary; это также должно войти в account
review. Redirects, env proxy и streaming выключены; bounded bytes/deadlines,
strict decision envelope и серверная подстановка identity сохраняются.

Raw input/output — только память операции, без DB/browser persistent storage,
logs/metrics/traces. Локальный deadline не доказывает удаление у provider.
`clarification/no_change/unsupported` не меняют intent и не списывают quota;
exact retry использует durable receipt, не повторяет model transport.

## Разделение режимов и оставшиеся решения

1. `finite`: прежний reproducible UI lab, конечные фразы, сеть закрыта.
2. `decision-transport-fixture`: тот же настоящий UI/HTTPS/backend/PG/Redis;
   общий adapter, используемый HTTPS eval, получает synthetic completion bytes
   через MockTransport. Это проверка композиции и failure lifecycle, не LLM quality.
3. Closed LIVE eval: прежний exact corpus gate и SAME durable journal; ни ключ,
   ни journal в UI lab не монтируются. Новых вызовов/резервов эта работа не делает.
4. Real-user outbound: BLOCKED. Готового разрешённого публичного parser нет.

Ответственный за одобрение — владелец Ttest; конкретный account/data owner пока
не назначен (`unassigned`). До real-user outbound он должен предоставить
не содержащие секретов account reference, договор/DPA и применимую юрисдикцию,
подтверждение training exclusion, регион/subprocessors/transfer safeguards,
точные retention и deletion SLA для input/output/logs/backups, процедуру удаления
и подтверждения выполнения, основание обработки и пользовательское уведомление.
Затем — отдельный review кода минимизации/egress, бюджета и isolated composition.
Этот JSON невозможно превратить в разрешение одной правкой значения.

Live UI smoke требует отдельного разрешения на точный synthetic сценарий,
тот же journal/budget и новую reviewed композицию с сетевым доступом. Предыдущие
24/24 не являются приёмкой UI и не разрешают arbitrary user text. Capacity
ISSUE-004 остаётся OPEN/BLOCKED; merge, production и public activation запрещены.

# Настоящий DeepSeek intent: первый закрытый прогон

1 ноября 2026, Europe/Moscow. Пользователь сообщил о добавлении ключа и поручил
продолжить ранее согласованный synthetic intent test. Прежний offline-only
отказ отменён в рамках этого теста. Ключ прочитан только локальным launcher,
передан через env-file одноразовому контейнеру; в evidence/Git его нет.

**FULL LIVE REGRESSION PASS: 24/24 на исправленных инструкциях.**
Начальный прогон 21/24 и targeted fix 3/3 сохранены ниже как отдельные результаты.

## Полный повтор после согласования лимита

Пользователь разрешил общий лимит **56 HTTP-попыток / $0.75 резервов**.
Source `3b476ce2ca556849e09a8332f55470d1cbb22b84` отличается от исправления
81a1fb30 только этими двумя числовыми лимитами. Prompt, corpus и эталоны прежние.
Перед live проверкой 32 offline closed-provider tests PASS, включая атомарный
лимит и сохранение резерва при restart/targeted test.

Полный повтор: **24/24 semantic PASS**, 14 правильных typed patches и 10
правильных clarification/no_change/unsupported. 24 новых HTTP-попытки, все с
usage, без retries/transport failures. Медиана parse latency 1982.21 ms,
максимум 5931.54 ms, сумма 56.594 s. Ни p95/SLO, ни UI/DB performance этим
малым provider-прогоном не сертифицируются.

[full-repeat-result.json](ai-intent-live-evidence/full-repeat-result.json),
[точный source/image/archive](ai-intent-live-evidence/full-repeat-source.json),
[итог и накопительный расход](ai-intent-live-evidence/full-repeat-summary.json).

В том же journal суммарно **51/56 попыток**, 51 ответ с usage, 184 094 input /
1134 output tokens. Peak/cache-miss estimate **$0.056589** за все три прогона,
не выписка billing. Полный не возвращаемый резерв **$0.564060 из $0.75**.
Резервы первых 27 попыток сохранены, журнал не пересоздавался.

Первый сценарий закрытого intent contour прошёл согласованный небольшой corpus.
Это не доказательство обобщения, не public activation и не приёмка настоящего
parser в UI/HTTP; голос также остаётся выключен. Прежние неуспешные результаты
не скрываются и не заменяются последним score.

## Первый результат

Source `16848a23f4349140f7a357eda15825e6d1e5aa84`, DeepSeek `deepseek-flash`,
non-thinking JSON mode. Точный исходный corpus/эталоны не менялись:
`7b722ab6caa0bf3377a0ace8fcddecf6daa7f7cb9bcebec515ab0cac9997d288`.
Отправлялась только согласованная синтетика, текущие typed criteria и фиксированная
схема/инструкции. Данные Flatio pilot, реальные объявления и пользовательские
сообщения не отправлялись. App runtime и UI не активировались.

24/24 HTTP-ответа с валидным usage, без retries/transport failures.
Полный semantic score **21/24 (87.5%)**, 12 typed patches — все соответствовали
эталону. Медиана parse latency 1643.445 ms, максимум 2150.79 ms; это один малый
последовательный provider test, не HTTP/SQL/browser performance certification.

Три несовпадения смысла/решения, без ложного допуска конфликтующих ограничений:

| Case | Ожидание | Фактический исход |
|---|---|---|
| ru-dog | pets: одна маленькая собака | лишнее clarification |
| es-cat | pets: один кот, размер unspecified | лишнее clarification |
| ru-conflict | clarification противоречия о балконе | unsupported |

Исходный результат сохранён неизменным: [initial-result.json](ai-intent-live-evidence/initial-result.json).
Частный текст reasoning/provider body не сохранялся; причину поведения модели
нельзя считать доказанной. Инструкции допускали слишком широкое требование
party composition и выбор unsupported для конфликта поддерживаемых условий.

## Исправление и ограниченная повторная проверка

Source `81a1fb303fe818d5bb7677dc9145cb8bf6fd8883` явно разделяет критерии:
pets не требует заполнения party/budget/mode; конфликт поддерживаемых условий
требует clarification. Corpus и эталоны сохранены. Добавлен --case-id для
подмножества того же согласованного corpus, с тем же hash/gate/journal.
Unknown case отвергается до credentials/IO; старые резервы не сбрасываются.

88 offline provider/evaluator tests PASS, Ruff изменённых Python files PASS,
mypy app: 159 source files PASS. Полный прежний unit/PG/browser набор на этом
исправлении повторно не запускался и не объявляется пройденным.

Повторены только ru-dog, es-cat, ru-conflict: **3/3 LIVE PASS**, без retries.
[targeted-result.json](ai-intent-live-evidence/targeted-result.json).
Это исправление наблюдавшихся случаев, не новый полный score 24/24 и не
проверка обобщения на незнакомые запросы. Full-corpus regression нового prompt
остаётся необходимым до семантической приёмки.

## Расход первых двух прогонов (исторический снимок до расширения)

Один persistent journal, всего **27 из 32** согласованных HTTP-попыток,
27 ответов с usage. Всего 96 307 input и 588 output tokens.
По peak/cache-miss ceiling $0.30/$1.20 за миллион оценка **$0.029598**;
она намеренно не учитывает скидки/cache и **не является выпиской billing**.
Тарифы сверены по [официальной странице](https://api-docs.deepseek.com/quick_start/pricing/).

Суммарный не возвращаемый резерв **$0.298620** из локального бюджета $0.50.
Осталось 5 HTTP-попыток: новый полный прогон в остаток не помещается. Лимиты,
journal и размер output не увеличивались; journal не удалялся/не заменялся.
Новый полный прогон потребует отдельного согласования дополнительных попыток
и резерва. Файл журнала остаётся локальным; в evidence только счётчики.

[Source metadata и итог](ai-intent-live-evidence/summary.json),
[проверки](ai-intent-live-evidence/provider.xml),
[SHA256SUMS](ai-intent-live-evidence/SHA256SUMS).
Raw timings и результаты обоих sources не объединяются в вымышленный общий pass.

Пункт 5 сохраняет самостоятельную приёмку закрытого Flatio pilot; здесь он не
перепроверялся. Пункт 3 пропущен / ISSUE-004 OPEN. Голос/ASR не подключались.
Merge, public AI, production DB, новый crawling/deploy не выполнялись.

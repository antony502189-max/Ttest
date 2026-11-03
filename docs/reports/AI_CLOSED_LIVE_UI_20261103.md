# Разрешённый synthetic LIVE UI smoke — FAIL

3 ноября 2026, Europe/Moscow. Пользователь явно разрешил пункт2: до3 provider
attempts, только три согласованные synthetic фразы, SAME journal и локальный
дополнительный резерв33180 microUSD. Это не разрешение real-user outbound,
новых данных или production. Проверка остановлена после первой реальной попытки.

**Итог: LIVE smoke не прошёл.** Нет успешных LIVE сценариев, typed результата
или LIVE cards/map acceptance. Остальные2 provider attempts не использованы;
автоматических retries, добора успешных случаев и сброса счётчиков не было.

## Фактический результат

| Показатель | До | После |
| --- | --- | --- |
| SAME journal attempts |51 |52 |
| Reserved microUSD |564060 |575120 |
| Attempts с подтверждённым usage |51 |51 |
| Новые успешные LIVE случаи |0 |0 |
| Новое списание пользовательской quota |0 |0 |

Одна новая попытка зарезервировала11060 microUSD ($0.011060) **до** provider IO.
Usage этой попытки не подтверждён. Это не доказательство нулевого provider bill;
reservation сохранён. Прежний global limit56/$0.75 не менялся. Дополнительных
модельных запросов для диагностики не было.

Тарифы сверены перед запуском с
[официальной pricing page](https://api-docs.deepseek.com/quick_start/pricing/):
`deepseek-flash`, peak cache-miss input $0.30/1M, output $1.20/1M. Согласованный
консервативный резерв не требовал повышения. Cache/off-peak скидки не учитывались.

## Два отдельных запуска

1. Source `5e053697997f0c215ca3353bd1aba631cef88488`: настоящий Chrome/UI/HTTPS
   дошёл до terminal `LLM_FAILURE`, **новых provider attempts=0**. SAME journal
   создан прежним eval от root и был readable, но не writable для UI uid999.
   Локальная диагностика с MockTransport и перехватом reserve доказала достижение
   reservation boundary без reserve/IO; исходные counters остались51.
2. Исправлен startup guard: writable файл и directory требуются **до** открытия
   ключа и создания transport. Source `cf483c4a88075fa38da46dd7988c41590beb3185`
   собран из clean git archive; source tar SHA256
   `d043e18185b0b7c78ffd83fb98fe945ae4e0b7650a87f0c067fafe3fcf8d4150`.
   Для этого запуска SAME SQLite-файлу временно назначен uid/gid999; hash его
   содержимого до/после изменения прав совпал. Backend продолжал работать
   непривилегированным. После первой фразы `ru-balcony` получен failed terminal
   outcome `LLM_FAILURE`; read-only status GET подтвердил failed, журнал52.
   Следующие `es-monthly` и `en-negation` не отправлялись.

Каждый запуск использовал отдельные immutable source/evidence paths. Ключ читала
только явная backend factory из read-only file mount; host не выводил значение.
Provider model transport не подменялся во втором запуске. Другие personal/user
texts, history, identity, SQL, expected answers и объявления не отправлялись.

Точный исходный HTTP status/provider failure code второй попытки не сохранён:
публичная граница намеренно выдаёт общий `LLM_FAILURE`, а контейнер заменён при
cleanup до сохранения диагностических данных. Поэтому нельзя утверждать, что
причина — credential, balance, latency, provider rejection или transport.
Одного факта reservation недостаточно для доказательства успешного ответа модели.

Диагностическая TLSv1.3 handshake с `api.deepseek.com` прошла за239ms через
certifi verification: **HTTP requests=0, credentials mounted=false**. Это
проверяет базовую TLS связность, не API account и не прошлый failed outcome.

## Исправления без дополнительных paid calls

- `ExistingSmokeBudget` отклоняет readable-but-unwritable journal до чтения key.
- Одноразовый LIVE driver требует reviewed manifest, exact corpus hash,
  исходные51/$0.564060 и `wx` marker; повторный запуск не создаёт новый бюджет.
  После failed/uncertain outcome — только status GET, без повторной inference.
- Добавлены диагностические сообщения только с HTTP status и фиксированными
  allowlisted failure codes. Provider bodies/headers, keys, arbitrary exception
  text, пользовательский ввод и operation identities не логируются.
- Driver сохраняет только эти JSON-log messages **до** замены LIVE контейнера;
  произвольные dependency logs в report не попадают. Неизвестная ошибка становится
  `PROVIDER_FAILURE`/`UI_PROVIDER_DEPENDENCY_FAILED`, без её текста.
- 55 targeted provider/lab checks и Ruff app/tests/lab прошли. Новые regressions
  проверяют writable guard, status401 с private canaries и неизвестную ошибку.
  Проверки выполнялись с disposable journals/MockTransport, не настоящим provider.

Код диагностики добавлен **после** failed LIVE runtime и не объявляется
проверенным на новом paid request. Прежние offline3/3 и main15/15 остаются
отдельными доказательствами и не превращаются в LIVE PASS.

## Cleanup и оставшиеся gates

Оба запуска завершили обязательный cleanup. Backend и frontend возвращены к
прежнему offline runtime `fb1877d3fc2aac7c7776bdb384b43d90c4022bf8`, mode
`decision-transport-fixture`. Backend снова только на internal lab network.
Key/budget mounts отсутствуют, отдельная LIVE egress network удалена. Исходный
владелец SAME journal восстановлен uid/gid0; counters52/$0.575120 сохранены.
Обе failed операции имеют used0/reserved0, без result receipt.

[Raw outcomes, quota и isolation evidence](ai-closed-live-ui-20261103-evidence/README.md).
Ключ/настоящая SQLite DB не входят в опубликованные artifacts.

LIVE UI gate остаётся OPEN/FAIL. Перед новым paid прогоном нужен отдельный
review и согласование поведения после этого failed outcome; действующий driver
не разрешает молча начать заново с baseline52. Journal не сбрасывать и не
переносить, unused allowance не считать новой свободной авторизацией.
Real-user outbound BLOCKED, account/DPA/no-training/region/retention unknown;
новый real catalog, production rollout и production-sized migration rehearsal
не разрешены/не закрыты. ISSUE-004 OPEN/capacity BLOCKED, нового benchmark нет.

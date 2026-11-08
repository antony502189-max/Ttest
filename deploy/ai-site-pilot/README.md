# Закрытый site-domain pilot · S2.1 / S3 / S6

URL: `https://app.112233.es/ai-pilot/#/`. Отдельные frontend/backend,
PostGIS0079, Redis, maintenance и state; основной сайт/DB0066 и sealed demo3/3
не обновляются. DNS/TLS/Traefik проверены на VPS, маршрут имеет только этот prefix.
HTTP Basic применяется ко всей странице, assets и API. Секрет доступа лежит в
локальном ignored `output/ai-site-pilot-20261108/private/access.txt`, не в Git.

## Состояние перед допуском

Страница и API доступны, модель заблокирована отсутствием `/pilot-control/approval.json`.
Ключ в pilot не установлен, attempts0. Не называть это выполненным real-model
ручным тестом. Новый approval для предложенных50/$1 пока требуется от владельца.
Наличие старого synthetic ключа и поручение работать до лимита сессии не разрешают
новый paid dispatch. Старые journals не читать/сбрасывать/подменять.

Данные: immutable public snapshot13unique PisoCompartido,08.11.2026 16:27MSK,
без аккаунтов/контактов/raw/descriptions; technical FK owner создан локально.
13price/rental-mode proofs через existing pipeline. Прочие карточные поля не
становятся AI facts. Никакого нового crawling. Freshness24h использует исходные
source timestamps: фактическое исчезновение возможно раньше snapshot+24h.
Standing refresh и весь каталог этим не приняты.

## Предлагаемый ограниченный допуск

Только владелец/команда, неперсональные rental test inputs. Positive grammar
принимает полную фразу бюджета50–1000 EUR/monthly наRU/ES/EN или снятие бюджета;
другой текст целиком отклоняется до IO. Provider получает заново собранную
английскую строку с одним числом и typed rental_mode/budget. Не отправляются
исходный текст, история, identity/session/result IDs, listings, IP браузера,
cookies, контакты или evidence. Это ограниченная test composition, не privacy
certification произвольного ввода. Public `RealUserOutboundDenied` не изменён.
Account/DPA/training/retention/transfer gates для реальных посетителей открыты.

Предложено50новыхattempts, local reserve ceiling1,000,000microUSD; до одобрения
никаких generation calls. Один transport attempt/operation,1024output tokens,
8sHTTP/10sparser/15sexecution/20sAPI. Peak цены сверены08.11 по
[официальной странице](https://api-docs.deepseek.com/quick_start/pricing/):
$0.30/1M input и$1.20/1M output. Conservative full reservation11060microUSD
наdispatch, максимум553000microUSD на50. Это локальный резерв, не invoice cap
провайдера и не сертификация tokenizer. Missing/invalid usage останавливает
дальнейшие dispatch. Same canonical input/session version нельзя оплатить повторно;
durable UI operation receipt сохраняет обычное idempotent recovery.

Backend имеет только internal Docker network. Единственный CONNECT proxy с
outbound сетью соединяет только `api.deepseek.com:443`; TLS end-to-end, без MITM
и логирования payload. Direct backend TCP blocked, wrong destination403,
non-billable provider TLS GET401 проверены. Это отдельный сетевой allowlist,
не прежняя широкая demo egress. Browser CSP ограничивает img/connect своим origin;
внешние фото показывают fallback, карта — existing coordinate renderer.

## Эксплуатация и rollback

VPS directory `/srv/112233-ai-site-pilot-20261108`, Compose project
`ttest-ai-site-pilot-20261108`. Команда:

```sh
cd /srv/112233-ai-site-pilot-20261108
docker compose --env-file deploy/ai-site-pilot/.env -f deploy/ai-site-pilot/compose.yml ps
```

После конкретного разрешения владельца установить ограниченный approval artifact
с binding из `pilot.budget.BINDING` и отдельно существующий тестовый ключ через
SSH stdin, owner999/mode400, только в `deploy/ai-site-pilot/control`. Не выводить
ключ/пароль/env/compose config в отчёты. Перед первым dispatch сохранить отдельные
DB dump и encrypted erasure/state backup; они не заменяют независимость erasure
journal в общем production restore protocol. Не переносить этот compose в обычный
production workflow или подключать primary DB.

При остановке сначала атомарно переименовать control/approval.json в
approval.disabled.json (если существует), затем остановить egress и перезапустить
backend, чтобы оборвать in-flight. Закрытие всего pilot: `compose stop frontend
backend maintenance egress`; Traefik удалит только отдельный pilot route. Основной
сайт продолжит прежний маршрут. Не применять down -v, не удалять journals/signing
keys/DB и не создавать новые state ради нового лимита. Для повторного включения
нужна сверка того же journal, не новая установка. После активации UI/модель/SQL/
уточнение/карта/reload проверяются на том же HTTPS URL и сохраняются receipts.

Обнаруженные при подготовке ошибки сохранены в отчёте: duplicate source join,
ORM replacing explicit NULL, неверная encoding первоначального erasure env и
nginx stale DNS после пересоздания backend. Это не потеря/reset budget journal.
Основные S0–S7/A1–A12, voice/saved/delivery/capacity/release gates сохранены.

# Закрытый site-domain pilot · S2.1 / S3 / S6

URL: `https://app.112233.es/ai-pilot/#/`. Отдельные frontend/backend,
PostGIS0079, Redis, maintenance и state; основной сайт/DB0066 и sealed demo3/3
не обновляются. DNS/TLS/Traefik проверены на VPS, маршрут имеет только этот prefix.
HTTP Basic применяется ко всей странице, assets и API. Секрет доступа лежит в
локальном ignored `output/ai-site-pilot-20261108/private/access.txt`, не в Git.

## Remediation PR411 — подготовлено, НЕ выложено

Новая версия кода отделена от действующего пилота до review/отдельного допуска
deployment. Она использует минимальный FastAPI только сAI routers иstatus,
закрывает всё остальное наNginx иASGI поmethod/path allowlist, не создаёт auth
refresh cookies. Frontend имеет отдельный entry/router/guest context/card,
безaccount hydration/publish/pay/admin/marketplace effects. Любой другойhash
перенаправляется наAI page; прямые API обходы получают403/404.

Свежесть проверяется read-only по existing verified predicates до parser и
непосредственно перед transport/reserve. Полностью неeligible каталог даёт
catalog_ready=false/PILOT_CATALOG_STALE, UI закрываетsubmit; SQL/business quota
не списываются. Это не standing refresh: исходные timestamps не продлеваются.

Доверенные hops: существующий Traefik проверен read-only08.11 как172.18.0.2;
builder требует явный проверенныйIPv4 peer, который рендерится вNginx какодин
address. Nginx принимаетreal-IP только отэтогоpeer, берёт rightmostXFF,
переписывает X-Real-IP иудаляет XFF/Authorization перед backend. Прямой вход
вNginx дляpilot denied. Backend доверяет только fixed frontend172.30.41.2/32.
Новый internal subnet172.30.41.0/28 иdynamic range172.30.41.8/29 исключают
столкновение сfrontend. При изменении сети не расширять trust на весьsubnet.
Сначала проверить отсутствие конфликта subnets иистинныйTraefikpeer.

Единая сборка из clean checkout:

```sh
node scripts/build-ai-site-pilot.mjs 172.18.0.2
docker compose --env-file deploy/ai-site-pilot/.env --env-file output/site-pilot-build.env -f deploy/ai-site-pilot/compose.yml build
```

Builder проверяетcleanGit, base/API prefix/mock=off, создаёт manifest сточнымSHA
иSHA256JS/HTML, рендеритpeer ипубликует build.env. Dockerfile сверяет SHA/mode
manifest сbuildarg; безbuilder/envfile сборка останавливается. Противоречивые
Viteenv отвергаются внутриconfig, отсутствиеenv даёт безопасныеpilot defaults.
Самостоятельный dockerbuild изстарыхdist не является release-процедурой.

Перевыпуск network topology требует отдельно разрешённого stop/recreate только
pilot services/network ссохранением тех жеpg/redis/state volumes, journals,
keys иapproval. Не применятьdown-v ине копироватьsnapshot поверхboundstate.
Полные инструкции/матрица: `docs/reports/PR411_REMEDIATION_20261108.md`.

Revocation: удаление/rename approval блокирует последующие проверки, но не
отзывает уже отправленный запрос. Обязательные два шага выполняетoperator-only
`python deploy/ai-site-pilot/revoke.py`: сохраняетrevokedartifact, останавливает
egress иперезапускает backend дляоборванныхin-flight. Budget reservations не
возвращаются; pendingusage требует сверки. Передreserve есть повторный approval
guard, но файл+сеть не объявляются атомарной транзакцией. ScriptвCI не запускает
production; test покрываетегопорядок сmock subprocess. Rollbackкстаройсетисначала
отключаетegress/approval, сохраняеттекущийbudget ивосстанавливаеттолькоimages/
config/network предыдущейверсии. Старыеbudget backups радирасхода не восстанавливать.

Storage prefix — **логическое namespacing**, не browser security boundary.
Origin общий ссайтом: произвольныйscript этогоorigin технически может читать
другиеключи. Вновойкомпозиции storagewrites ограниченыpilot language/AI locators;
проверяютсяfavorites/drafts/saved/language/media/continuation иcomputedthirdparty
sentinels. Длясильнойorigin isolation нуженотдельныйorigin, здесьоннеобещается.

## Наблюдения счётчиков действующего прежнего пилота

Источник истины — persistent provider SQLite; наружная read-only проекция:
authenticated GET `/ai-pilot/api/v1/private-demo/status`. На08.11.2026
18:45:10UTC (21:45:10MSK):7/50,43осталось,approved=true/halted=false.
Это наблюдение, не обещание неизменного остатка. Credentials redacted,
raw receipt — reports/pr411-remediation-20261108-evidence/current-status.json.
Следующий текст4/50 относится ТОЛЬКО краннему завершённому показу около14:01UTC:

Владелец явно разрешил50новыхобращений/$1 именно в предложенном scope.
Approval/key установлены; real HTTPS flow600→12/400→3/remove→13, карта/reload
иmobile owned-result restoration PASS.Исторически4/50attempts,44240microUSD reserve,
тогдаоставалось46attempts. Provider usage4/4, raw input не отправляется.
Пилот оставлен активным в той же composition/journal; не удалять/не сбрасывать
journal ради нового лимита. На каждого гостя сохраняется3успешныхоперации/день,
независимо от общего provider budget. Фото закрыты CSP, snapshot стареет по
исходным timestamps. Полный public/account/standing-data/release gate не закрыт.

## Состояние перед допуском · историческое

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

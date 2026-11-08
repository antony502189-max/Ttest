# S2.1 / S3 / S6 · защищённый pilot на домене сайта

08.11.2026 подготовлена реально доступная HTTPS-страница
`https://app.112233.es/ai-pilot/#/`, закрытая HTTP Basic для страницы/assets/API.
Это не прежний localhost tunnel и не synthetic каталог. **Новая модель пока
не активирована: требуется конкретный новый spending/test-input допуск владельца;
запрошены50attempts/$1 на неперсональные rental tests через существующий тестовый
аккаунт. Ответ пока не получен. Новых generation calls0.**

Ветка `codex/ai-search-site-pilot` продолжает merged main345b7ca8. Прежние
review409/410 не повторялись. Owned final docs сохранены отдельным commit перед
созданием ветки, чужие dirty changes старого root checkout не менялись.

## Что реально работает без новой оплаты

- DNS `app.112233.es` →169.58.147.65, existing Traefik/HTTPS. Только route
  `Host(app.112233.es) && PathPrefix(/ai-pilot)`, отдельный frontend8443.
- Unauthenticated401; authenticated desktop1440 и mobile390 страницы открыты,
  JS errors/HTTP5xx0. UI показывает pending approval, submit заблокирован.
- Гостевая identity/session, secure/HttpOnly/SameSite cookie с отдельным
  `/ai-pilot/api/v1/ai-search` path, verified SQL cards13/13 и map1cluster
  через настоящий HTTPS API. Quota remaining3, model calls0. Test session закрыта.
- Отдельная DB0079, Redis и maintenance; source snapshot13unique/public
  PisoCompartido от08.11 16:27:23MSK,13query proofs. Нет account/contact/raw/description
  export, crawling или копирования основной DB. Snapshot стареет по исходным
  timestamps, standing refresh не заявлен.
- Backend только internal network; direct TCP egress blocked. Отдельный CONNECT
  proxy отверг example.com, разрешил TLS GET api.deepseek.com401 без generation.
  Ключ не загружен, approval artifact отсутствует, journal attempts0/reserve0.
- Pipeline/currentness/typed matching/quota/receipt остаются существующими.
  Positive grammar реконструирует только English rent command + число50–1000;
  исходный input/identity/listings не пересылаются. Unknown input отвергается
  целиком. Это scoped nonpersonal test gate, не public privacy certification.

## Исправления, найденные на реальном пути

Первый14-row export имел13unique listings: две активные source записи одной
карточки. Исправлен join через детерминированный LATERAL latest-success/id,
следующий snapshot13создан отдельно; failed export сохранён, не импортирован.

ORM defaults превращали явные source NULL в furnished=true/room_capacity=1 и
подобные значения. Seeder теперь вставляет SQL NULL явно. До ремонта отдельной
pilot DB сохранены dump/state backup;103nullable fields приведены строго к
bound immutable snapshot, snapshots/keys/journals не сбрасывались. Проверка
`verify_catalog` затем прошла, seeder resumed до13proofs/completed. Добавлен
disposable PG regression с repeated seed и неизменными state bytes.

Первоначальный новый erasure env имел hex encoding, а runtime требует base64
32bytes. До создания erasure journal преобразована кодировка тех же bytes,
не заменён секрет. Ошибка остановила seed, повторный запуск продолжил его.

После пересоздания backend nginx держал прежний DNS IP; добавлены Docker
resolver/variable upstream. Mobile onboarding обычного сайта скрывал pilot page;
только pilot build выключает этот shell и использует responsive existing AI
dialog. Homepage выделена под проверку AI, continuation storage namespace отдельный.

## Проверки и пределы

Финальные локальные62targeted backend PASS; новый disposable PostGIS seed test1PASS
за15.41s; dedicated site-pilot browser8PASS (390/1440 × pending/approved/unavailable/
malformed status), actual HTTPS desktop/mobile/API PASS. Approved-state browser
case имеет intercepted API и не считается реальным model acceptance. Ruff,
oxlint (6pre-existing warnings), i18n guard и tsc-b PASS, pilot Vite build PASS
(existing chunk-size warning). Новый точный CI ещё не подтверждён.

Raw proof/screenshot/XML/hash attestation:
[evidence](ai-site-pilot-20261108-evidence/https-ui-proof.json),
[API](ai-site-pilot-20261108-evidence/https-api-proof.json),
[network](ai-site-pilot-20261108-evidence/network-proof.log),
[PostGIS](ai-site-pilot-20261108-evidence/pilot-null-pg.xml).
Секреты и snapshot в evidence/Git не входят. Access credentials только в локальном
ignored `output/ai-site-pilot-20261108/private/access.txt`.

VPS `/srv/112233-ai-site-pilot-20261108`, Compose
`ttest-ai-site-pilot-20261108`. [Configuration/rollback](../../deploy/ai-site-pilot/README.md).
Основной frontend1292c680/production DB0066 и sealed demo3/3 не менялись. Существующий
runtime backend сверяется SHA256 с локальными файлами отдельно от Git/CI.

Следующий конкретный шаг — после нового owner spending/input approval установить
scoped approval/key в уже подготовленную composition, затем пройти настоящие
HTTPS UI→DeepSeek→SQL→уточнение→карта/reload с тем же новым pilot journal.
Без ответа paid IO не выполнять. Public real-user rollout, полные S2/S3/S6,
account/data/performance/release и voice/saved/delivery/A1–A12 остаются открытыми.

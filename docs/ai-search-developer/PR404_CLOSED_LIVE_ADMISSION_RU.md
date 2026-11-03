# PR404: допуск закрытого LIVE smoke после ревью 03.11

Этот документ не разрешает запуск, расход бюджета, production или передачу реальных пользовательских данных. Подготовка к merge lab-only кода отделена от LIVE-приёмки.

## F1/F4: доступ, pairing и маршруты

Поля `lab-runtime` публичны и служат только совместимости релизов. Они не являются паролем. Для реального закрытого режима предусмотрены два отдельных барьера:

1. Loopback nginx в `closed-ui.nginx.conf` требует клиентский сертификат доверенного operator CA (`ssl_verify_client on`). Обычный offline compose этот конфиг не использует.
2. Nginx перезаписывает `X-AI-Lab-Access` приватным случайным 256-bit значением; backend проверяет его constant-time до AI-операции. Браузеру значение не передаётся. Поддельные/дублированные заголовки не принимаются. Публичный attestation можно прочитать, но его replay без proxy credential не допускает inference.

Custodian готовит отдельную read-only директорию `CLOSED_UI_ACCESS_DIRECTORY` с `client-ca.crt` и `proxy.conf`. Формат include строго один: `proxy_set_header X-AI-Lab-Access "<64 lowercase hex>";`. Значение генерируется криптографически случайно вне репозитория, не используется как публичная константа. Private CA/operator keys не монтируются в backend; browser smoke получает пути к операторскому сертификату/ключу через приватный run manifest.

Backend не публикует host ports. Только frontend публикует127.0.0.1:9443; внутренние сети не содержат недоверенных контейнеров. Публикация backend/изменение сети требует нового review. `proxy_pass http://backend:8000` сохраняет исходный URI. Middleware защищает точный корень `/api/v1/ai-search` и все его подпути; WebSocket в этом namespace запрещён. Других inference routes/WS при изменении router composition добавлять без нового review нельзя. Guest/auth ownership, Origin и quota остаются отдельными обязательными проверками.

## F5: исходный journal и локальные writers

Device/inode/path проверки остаются проверками идентичности, **не** атомарной привязкой SQLite к file descriptor. Такая гарантия не заявляется.

LIVE-допуск требует выделенного непривилегированного UID без недоверенных процессов того же UID, единственной private journal directory и отсутствия других недоверенных RW mounts. На Linux код отвергает symlink, не regular file, чужой UID, group/other-writable файл или родительскую директорию. Каталог должен разрешать SQLite sidecar/locks только доверенным evaluator/UI-процессам. Предки каталога и bind mount проверяются оператором; широкие chmod777 не допускаются. Доверенный процесс с тем же UID и host administrator находятся вне этой модели доверия; если такое исключение неприемлемо, LIVE остаётся закрытым до выделенного journal broker/VFS.

Исходный journal не копировать, не сбрасывать и не заменять. Новые проверки межпроцессной конкуренции/restart используют только DISPOSABLE journal. Windows unit tests не подтверждают Linux ownership/mode; этот тест должен пройти в Linux CI/контейнере.

## F6: независимая проверка расходов и egress

Подпись custodian удостоверяет его утверждения, а не фактическую настройку провайдера. Код не обращается к billing API и не объявляет hex-хеш доказанным spending cap.

Перед подписью точного release независимый оператор обязан:

- Проверить фактический account/project, область действия dedicated credential и billing limit именно этой области; архивировать receipt/экран настройки в приватном evidence.
- Проверить, что limit реально принудительный, а не только уведомление; если такого механизма нет — не подписывать `provider_limit_verified=true` и не запускать LIVE по этой политике.
- Проверить актуальные ставки, суммарный spent/reserved и исходный SAME journal. Последняя известная реальная история —52attempts/$0.575120reserved; не возвращаться к51.
- Проверить egress: только утверждённое назначение, без redirects/proxy-env; фактические сети, mounts, секреты, non-root UID, mTLS и закрытый backend.
- Сохранить отдельный `operational-review.json`, подписать его SHA256 в `external_cap_evidence_sha256` admission, а также source/image identities и срок допуска. Не заполнять review предположениями.

Review schema `ai-closed-ui-operational-review.v1`: точные поля `schema`, `source`, `account_reference`, `billing_scope`, `reviewer`, timezone-aware `verified_at`/`expires_at` (окно≤1ч), integer `external_cap_micro_usd` и true-поля `provider_limit_verified`, `credentials_scope_verified`, `egress_reviewed`, `client_access_reviewed`, `journal_permissions_reviewed`. Reference не содержит секретов; конкретные receipts остаются в приватном custody. Отсутствие, чужой хеш/source/cap, expiry или неподтверждённый пункт отвергаются и host preflight, и factory до чтения provider key.

Host CLI теперь требует `--operational-review <private-file>`. Factory читает `/closed-ui-admission/operational-review.json`. Run manifest для `smoke-ai-closed-live-ui.mjs` дополнительно требует `operationalReview`, `clientCertificate`, `clientKey`. Скрипт не генерирует signer, ключи или положительный account review.

## F2/F7/F8: доказательства и воспроизводимость

`scripts/ai-lab-input-policy.mjs` классифицирует все отслеживаемые/новые входы. Включены целиком backend/src/scripts/deploy/public/.github и корневые конфиги/build files; docs/reports/artifacts/tests/qa явно отделены. Новый неизвестный корневой каталог требует review. Манифест `docs/reports/pr404-review-fixes/runtime-inputs.json` содержит каждый включённый Git blob. CI отвергает неучтённое добавление/изменение/удаление. Изменение самого policy/verifier тоже входит в манифест и требует review.

Исторические source/artifact hashes проверяются на историческом runtime. Новые изменения не объявляются ранее проверенными Docker images: вывод `historicalEvidenceAppliesToCurrentRuntime=false` требует новой независимой container/stack проверки. `scripts/attest-ai-lab-containers.mjs <source> <backend-container> <frontend-container> <new-output>` отдельно инспектирует фактические image IDs/digests, env names/допустимые значения, сети/порты/mounts и hash effective config без raw secrets. Скрипт read-only, не запускает модель и не доказывает прохождение сценариев или наличие provider billing cap.

Frozen corpus/cases/51→54 fence и reservation заданы в одном immutable `backend/lab/closed_ui_spec.py`, версия `ai-closed-ui-experiment.v1`; тест сверяет их с provider policy. Новая версия эксперимента требует явного review и нового допуска, не синхронных неявных правок констант. HTTP2xx diagnostics теперь INFO; отказы WARNING, без body/header/token/text.

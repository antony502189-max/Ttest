# Закрытая демонстрация 08.11.2026

Владелец явно разрешил три фиксированные фразы и дополнительный предел $0.10.
Это отдельный private demo, не production activation и не real-user outbound.
Существующий `app.main` не включает этот factory. Нельзя сбрасывать provider
journal или создавать новый стенд ради обхода использованных трёх попыток.

Результат настоящего UI→DeepSeek→SQL:600€/мес→11,400€/мес→3,без бюджета→12.
Каталог — снимок12 публичных PisoCompartido от08.11 01:51MSK, не synthetic
listings. Это отдельная копия, не постоянное live чтение production. Контакты
и аккаунты не экспортируются; technical owner только связывает FK в demo DB.
Price-only mapping проверяет числовое согласие source text и existing import
price/currency/period/mode; прочие legacy booleans не становятся AI facts.
Cadence берётся из importer.price_period, без новой проверки внешней страницы.

Стенд на VPS: `/srv/112233-ai-private-demo-20261108`, Docker Compose project
`ttest-ai-text-demo-20261108`. Port19444 привязан только к127.0.0.1 VPS.
Локальный URL: `http://localhost:9444/#/` через encrypted SSH forwarding.
Обычный сайт, его БД, контейнеры, migrations и public routes не изменялись.

После трёх обращений backend переведён в режим без ключа и внешней сети.
Результаты/страницы/карта могут перечитываться без модели. Новый текст не
вызывает provider. Его model budget исчерпан независимо от дневной guest quota;
не обещать новые запросы по обычному счётчику «осталось поисков».
Existing result tab оставлена открытой; новая вкладка открывает landing,
а не автоматически чужую owned session. Для показа сохранены screenshots.

На сервере всегда использовать readonly override:

```sh
cd /srv/112233-ai-private-demo-20261108
docker compose --env-file deploy/ai-text-demo/.env \
  -f deploy/ai-text-demo/compose.yml \
  -f deploy/ai-text-demo/readonly.override.yml ps
```

Если локальный tunnel закрыт, из PowerShell можно снова открыть отдельный SSH:

```powershell
ssh -N -L 9444:127.0.0.1:19444 -o BatchMode=yes -o StrictHostKeyChecking=yes root@169.58.147.65
```

HTTP существует только на loopback; внешний участок проходит по SSH. Browser
certificate exceptions, Windows certificate/security changes и публичное
открытие demo порта не нужны. Карта — существующая координатная сетка с реальными
маркерами verified SQL API, без Google/внешних тайлов и без fixture markers.

Expiry/freshness guards продолжают действовать, поэтому с возрастом снимка
карточки исчезнут. Повторный snapshot/вызовы модели/расширение фраз требуют
нового конкретного разрешённого scope, а не сброса текущих счётчиков.

Полные provider/account/data/quality/performance/release/voice/saved/delivery
gates этим небольшим показом не закрыты. Журнал старого synthetic smoke не менялся.

## Исправления review409/410

Новая версия seeder связывает immutable snapshot SHA с PostgreSQL state
`starting → imported → proofs_ready → completed`. Повторный запуск на том же
снимке возобновляет существующие jobs/proofs; готовый import только проверяется.
Signing keys публикуются атомарно и сохраняются. Другой снимок, чужой каталог,
изменённые поля, отсутствующие bound keys/journals требуют разбирательства:
не удалять volume, не генерировать замену и не обнулять счётчики. Сначала
сохранить DB/state backup и сверить snapshot SHA, phase и существующие файлы.
После kill running job ждёт прежний lease и получает новый fencing token;
исчерпание двух попыток требует ручной сверки, а не нового job/бюджета.

Три платных шага закреплены за одной session и версиями 0/1/2 в SQLite.
Reserve записывается до HTTP; следующий шаг открывается только после валидного
семантического результата предыдущего. Ошибка, lost ACK или pending reservation
останавливают сценарий без refund. Если SQL continuation не сохранил результат
после успешного parser, платный шаг также нельзя повторить: требуется сверка.
Новая сессия не начинает заново расходовать первый шаг. Старый journal 3/3
доступен для чтения без миграции; частичный legacy journal не усыновляется.
При потере journal приложение не создаёт новый. Status UI показывает отдельный
лимит модели и недоступность стенда; карты/страницы не требуют новой модели.

В Compose больше нет пароля по умолчанию. Для новой согласованной установки
`AI_DEMO_DATABASE_PASSWORD` должен содержать 64 случайных lowercase hex символа
(32 bytes из `secrets.token_hex(32)`), в защищённом `.env` вне Git с mode600.
Не передавать значение в командной строке/PR/log. Отсутствующее значение
останавливает Compose; startup проверяет driver/host/role/database/secret.
Простая смена `.env` не меняет пароль существующего PostgreSQL volume: при
отдельном release сначала сохранить backup и согласованно сменить пароль
только роли ai_demo, затем обновить private env и приложение. Journal, signing
keys и provider approval при этом сохраняются. Исходный sealed стенд 3/3
этим изменением исходников не передеплоен; его ключ/egress не возвращались.

Private nginx CSP ограничивает browser img/connect/script собственным origin;
CDN-фотографии могут отображать fallback. Это отдельная защита браузера.
Live Compose всё ещё имеет широкую backend egress сеть до readonly override;
exact provider transport — application guard, не сетевой allowlist. Поэтому
всегда сохраняется readonly override для завершённого показа. Перед расширением
требуются отдельный reviewed account/privacy scope, сетевой egress control,
source quality/freshness и spending/invoice controls. SQLite estimate и local
volume не доказывают invoice cap или восстановление после полной потери диска.

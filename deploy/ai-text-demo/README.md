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

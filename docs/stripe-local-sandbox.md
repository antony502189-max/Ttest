# Локальная проверка Stripe в песочнице

Этот стенд запускает отдельные контейнеры и тома `ttest-stripe-test`. API и PostGIS доступны только через `127.0.0.1`; внешний импорт объявлений выключен. Публичный сайт и производственная БД не используются. Баннер остаётся на модерации после оплаты.

## Подготовка Windows и Stripe

1. Установите и запустите [Docker Desktop для Windows](https://docs.docker.com/desktop/setup/install/windows-install/) с Linux containers. Если WSL 2 ещё не установлен, в PowerShell администратора выполните `wsl --install` и перезагрузитесь при запросе. Проверьте `docker compose version`.
2. Установите [Stripe CLI](https://docs.stripe.com/cli/install): `npm install -g @stripe/cli`. Выполните `stripe login` и подтвердите вход в браузере. Через `stripe login list` и при необходимости `stripe switch` выберите нужную песочницу. Если вход запрещён, администратор Stripe должен разрешить CLI в Settings → Team and security → MCP and CLI access.
3. В нужной песочнице Stripe откройте Developers → API keys и раскройте **secret test key** `sk_test_` ([справка Stripe](https://docs.stripe.com/keys)). Не используйте `sk_live_` и не отправляйте ключ в чат.
4. В отдельном окне PowerShell запустите и оставьте работающим:

   ```powershell
   stripe listen --events checkout.session.completed,checkout.session.async_payment_succeeded,checkout.session.expired,checkout.session.async_payment_failed --forward-to http://127.0.0.1:18000/api/v1/payments/stripe/webhook
   ```

   CLI покажет локальный секрет подписи `whsec_`. Его не нужно регистрировать как публичный webhook в Dashboard. Если выбран другой аккаунт/песочница, перепроверьте `stripe login list` и `stripe switch`.
5. В каталоге репозитория выполните `powershell -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\set-stripe-test-secrets.ps1`. В скрытые запросы последовательно вставьте `sk_test_` из песочницы и `whsec_` из работающего CLI. Скрипт проверит префиксы и сохранит их в игнорируемый Git файл `.stripe-test.secrets` с доступом только текущему пользователю. Не передавайте секреты аргументами командной строки.

## Запуск

Из корня репозитория в PowerShell:

```powershell
docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml up -d --build postgres redis mailpit migrate backend
docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml ps
Invoke-WebRequest http://127.0.0.1:18000/health/ready
npm run dev -- --mode stripe-test --host localhost --strictPort
```

Первый запуск собирает Python-образ и скачивает PostGIS, поэтому может занять время. Миграции, включая `0057_payment_orders`, выполняются сервисом `migrate`. Если нужна локальная демо-учётная запись, в другом окне выполните `docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml --profile tools run --rm seed`; пароль демо-пользователей берётся из `backend/app/commands/seed.py`, по умолчанию `demo112233`. Демо-учётные записи используются только в этом отдельном томе.

На ноутбуке, где уже есть локальный образ `ttest-backend:latest`, можно не скачивать Python-зависимости повторно. Добавьте к командам Compose `-f docker-compose.stripe-test.cached-image.yml` после основного `-f` и запускайте `up -d --no-build migrate backend`. Override подключает текущие файлы `backend/app` и миграций только для чтения. Это локальный запасной путь при сетевой ошибке сборки; для выпуска образ требуется пересобрать обычным способом.

Откройте `http://localhost:5173/#/`. Фронтенд в режиме `stripe-test` обращается к API на порту 18000 и не включает демонстрационный mock mode.

## Проверка покупок

1. Войдите как локальный владелец, создайте и опубликуйте своё объявление, откройте «Mis anuncios» и запустите TOP на 1 день. На странице Stripe проверьте сумму **1 €**. Используйте [тестовую карту Stripe](https://docs.stripe.com/testing) `4242 4242 4242 4242`, любую будущую дату и трёхзначный CVC. После возврата убедитесь, что CLI получил `checkout.session.completed` с ответом `200`, а объявление стало TOP. Для пакетов 7 и 30 дней используйте отдельные объявления или завершите прежние незаконченные сессии; ожидаемые суммы **5 €** и **10 €**.
2. Создайте рекламный баннер с изображением через «Publicar publicidad». Перед оплатой проверьте **1 €** за 1 день; оплатите той же тестовой картой. После webhook кампания должна стать `pending_review` / `paid`, но не появиться публично до одобрения. При семи занятых местах новая оплата недоступна; предложена подписка на освобождение места.
3. Проверьте сохранённые результаты без вывода секретов:

   ```powershell
   docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml exec -T postgres psql -U ttest -d ttest_stripe -c "SELECT kind, days, amount_cents, status, paid_at FROM payment_orders ORDER BY created_at DESC LIMIT 10;"
   docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml exec -T postgres psql -U ttest -d ttest_stripe -c "SELECT listing_id, starts_at, ends_at FROM listing_promotions ORDER BY starts_at DESC LIMIT 5;"
   docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml exec -T postgres psql -U ttest -d ttest_stripe -c "SELECT status, payment_status, starts_at, ends_at FROM commercial_advertisements ORDER BY created_at DESC LIMIT 5;"
   ```

Завершение: `docker compose --project-name ttest-stripe-test --env-file .stripe-test.secrets -f docker-compose.stripe-test.yml down` сохраняет локальные данные для повторной проверки. Остановите `stripe listen` через Ctrl+C. Не используйте `down -v`, если нужны результаты проверки.

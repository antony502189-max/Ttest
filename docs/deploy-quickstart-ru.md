# Деплой 112233.es через GitHub Actions — инструкция для разработчика

> **Основной способ выкладки:** GitHub Actions, без ручного SSH-деплоя при обычном релизе. Это **ручной запуск**, после которого GitHub и VPS автоматически выполняют проверки, резервное копирование и обновление. Слияние PR в `main` **само по себе не обновляет сайт**.
>
> Production: **https://app.112233.es**. Репозиторий: **[antony502189-max/Ttest](https://github.com/antony502189-max/Ttest)**. GitHub Environment: `production`.

## 1. Что делать для каждого релиза

1. Разрабатывай задачу в отдельной ветке, создай PR в `main`. Дождись **зелёных CI-проверок** на последнем коммите PR; проверь изменения и объедини PR.
2. Убедись, что предыдущий деплой/бэкап/откат на VPS **не выполняется**. Если GitHub Actions уже показывает запущенный релиз — **не запускай ещё один**.
3. Открой **[Actions → Production deployment (manual approval)](https://github.com/antony502189-max/Ttest/actions/workflows/manual-production-deploy.yml)**.
4. Нажми **Run workflow**, выбери **`main`**, поставь галочку **I approve deployment of the current main to app.112233.es**, затем снова нажми **Run workflow**.
5. Дождись зелёного этапа **Confirm exact main commit and passing PR CI**. Ошибка этого этапа означает: на VPS **ничего запускать нельзя**; смотри логи проверки, исправь причину, при необходимости запусти новый workflow.
6. Если появилось **Waiting for review**, открой текущий запуск → **Review deployments** → отметь **production** → **Approve and deploy**. При текущем режиме самостоятельного подтверждения `Prevent self-review` должен быть **выключен** в настройках GitHub Environment. Если он включён, сам автор запуска подтвердить его не сможет.
7. Дождись завершения **Deploy manually approved release to VPS** с зелёной галочкой. Во время этого этапа **не меняй `main`**: сервер требует точного совпадения `origin/main` с проверенным SHA. Не прерывай работающий релиз и не нажимай повторный запуск.
8. Проверь [https://app.112233.es/build-info.json](https://app.112233.es/build-info.json) и вручную протестируй изменённую функциональность на сайте. Зелёный workflow без браузерной проверки новой функции — ещё не полная приёмка.

**Ключевое различие:** **Merge PR** = обновили код GitHub; **Run workflow** = запросили релиз; **Approve and deploy** = разрешили production; **зелёный Deploy + совпадение SHA** = релиз установлен.

## 2. Схема процесса

```text
Ветка разработки → Pull Request → проверка CI → Merge в main
                                                  │
                                                  ▼
GitHub Actions → Production deployment → Run workflow (main + галочка)
                                                  │
                                      Verify exact SHA + PR CI
                                                  │
                               Waiting for review (если включено)
                                                  │
                                    Approve and deploy
                                                  │
                    SSH с ограниченной командой → Contabo VPS
                                                  │
             Проверка блокировки/бэкапов → immutable release
                                                  │
                  миграции → контейнеры → health/smoke
                                                  │
           GitHub Success + current SHA + build-info.json
```

## 3. Кто может запускать и подтверждать

- Для **запуска** нужен доступ к Actions в репозитории.
- Окружение должно называться **строго `production`** и разрешать деплой только с `main`.
- Чтобы **один владелец самостоятельно запускал и подтверждал**: в **Settings → Environments → production** включить **Required reviewers**, назначить этого владельца и **снять `Prevent self-review`**. При включённом `Prevent self-review` потребуется **другой** назначенный ревьюер.
- Если **Required reviewers выключен**, после проверки CI деплой начнётся **без второго клика**; явное подтверждение в **Run workflow** остаётся обязательным. Не отключай защиту без согласования с владельцем.
- По возможности оставить отключённым **Allow administrators to bypass configured protection rules**. Правила окружения и секреты находятся в GitHub Settings, не в исходном коде.

**Разработчику для обычного релиза не нужно** знать серверный пароль, копировать SSH-ключи, открывать `production.env`, вручную выполнять Docker-команды или менять параметры Stripe.

## 4. Как понять, что релиз прошёл

В GitHub Actions должны быть зелёными **оба** job: `Confirm exact main commit and passing PR CI` и `Deploy manually approved release to VPS`.

Если есть одобренный доступ к VPS, оператор дополнительно выполняет **только чтение** в Linux SSH-терминале:

```bash
hostname
readlink -f /srv/112233.es/current
curl -fsS https://app.112233.es/build-info.json
cat /srv/112233.es/releases/<ПОЛНЫЙ_SHA>.deploy-info
```

Проверяем: hostname `vmi3640228`, `current` указывает на `/srv/112233.es/releases/<ПОЛНЫЙ_SHA>`, в файле метаданных есть `status=success`, публичный `build-info.json` сообщает **тот же SHA**. Не копируй `<ПОЛНЫЙ_SHA>` буквально: подставь SHA из запуска GitHub Actions. См. [полный deployment runbook](deployment.md).

## 5. Частые ситуации

| Симптом | Значение и действие |
| --- | --- |
| **Waiting for review** | Проверка прошла; необходимо нажать **Review deployments → Approve and deploy** согласно правилам окружения. |
| **Нельзя подтвердить свой запуск** | Проверь `Prevent self-review`; для самоодобрения он должен быть выключен, а запускающий пользователь — в списке ревьюеров. |
| **Сразу ошибка на verify-release** | Проверь checkbox, ветку `main`, свежесть SHA и успешный CI *того PR, которым получен этот merge commit*. Прямые пуши в `main` без подтверждённого PR могут быть отклонены. |
| **main changed; start a fresh release review** | После запуска `main` изменился. Не пытайся обойти проверку; дождись завершения предыдущей операции и создай свежий запуск для нового SHA. |
| **Missing production SSH private key / pinned VPS SSH host key** | Проверь **Settings → Environments → production → Environment secrets**; секреты должны называться `PRODUCTION_SSH_PRIVATE_KEY`, `PRODUCTION_SSH_KNOWN_HOSTS`. Значения не показывай и не присылай в чат/issue. |
| **SSH permission denied / host key verification failed** | Разобраться с ограниченным SSH-ключом или проверкой ключа VPS должен администратор; **не отключай StrictHostKeyChecking** и не меняй права `authorized_keys` наугад. |
| **Deploy завис или SSH оборвался** | Не запускай повторно: release может продолжать работу как systemd unit. Администратор проверяет unit, журнал, lock, метаданные и публичный SHA. |
| **Deploy failed / откат** | Сохрани логи без секретов, проверь действующий `current`; не запускай вручную миграции и не удаляй Docker volumes/резервные копии. Обращайся к [устранению неполадок](troubleshooting.md) и [операциям VPS](production-operations.md). |
| **Workflow зелёный, но функциональность не видна** | Сравни `build-info.json`, полный SHA, кеш браузера, health и UI; не инициируй повторный деплой вслепую. |

## 6. Одноразовая настройка (только владельцу/администратору)

Настраивается **один раз**: GitHub Environment `production` с `main` и правилами ревью; VPS → GitHub Deploy Key **read-only**; отдельный SSH-ключ GitHub Actions → VPS с `authorized_keys` командой `command="/usr/local/sbin/112233-manual-production-deploy",restrict`; root-owned серверный runner с правами `0700`; два Environment secrets `PRODUCTION_SSH_PRIVATE_KEY` и `PRODUCTION_SSH_KNOWN_HOSTS`. Нельзя публиковать приватные ключи, вывод `production.env` или создавать PAT внутри URL `origin`.

Подробная инструкция повторной установки/ротации: [Manual production CI/CD](manual-production-cicd.md). Реальный workflow: [`.github/workflows/manual-production-deploy.yml`](../.github/workflows/manual-production-deploy.yml).

## 7. Ограничения и ответственность

- Нет автодеплоя по `push` или `merge`. Это **ручной контролируемый релиз с автоматизированным исполнением**.
- Workflow допускает только актуальный `main` и проверенный merged PR; при изменении `main` после утверждения отменит устаревший релиз.
- VPS-скрипт поддерживает блокировку операций, резервные копии PostgreSQL/MinIO, миграции, smoke checks и управляемый rollback приложения; **rollback не откатывает необратимые изменения данных**.
- **Никаких** `docker compose down -v`, `docker volume prune`, удаления бэкапов, обхода lock, замены секретов или тестовых платежей в рамках обычного релиза.

См. [чек-лист релиза](release-checklist.md), [операционные инструкции](production-operations.md), [мониторинг](production-monitoring.md).

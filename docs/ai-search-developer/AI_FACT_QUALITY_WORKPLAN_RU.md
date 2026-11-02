# Пункт 5: независимая подготовка качества каталога

1 ноября 2026, Europe/Moscow. Подготовка возможна до живой проверки пункта 4.
Этот документ не разрешает crawling, real-content ingestion или исходящие
данные. Пункт 4 live пока не принят; пункт 5 принят в согласованном Flatio pilot scope
(итоговое обновление ниже). Исторический offline план сохранён.

## Проверенная исходная база

- `backend/app/services/ai_listing_input.py`: нормализация listing input и
  упаковка текстовых/структурированных evidence.
- `backend/app/schemas/ai_fact_bridge.py` и `services/ai_fact_bridge.py`:
  provider field policy, преобразование входа в наблюдения, поддерживаемое
  подмножество полей. Наличие parser не доказывает реальное coverage источника.
- `backend/app/schemas/ai_listing_facts.py`: explicit_allow, explicit_deny,
  conditional, unknown, conflict, legacy_unverified; происхождение и evidence.
- `backend/app/repositories/ai_fact_pipeline.py` и `ai_query_proofs.py`:
  публикация/актуальность facts и подготовка proofs. Существующий synthetic
  стенд уже использует этот путь, реальное покрытие каталога не измерено.

## Следующая offline работа без ключа

1. Матрица «существующий source adapter × поле»: что извлекается явно,
   какое evidence сохраняется, что остаётся unknown/unsupported. Разделять
   возможность parser, результат fixture и измеренное real-source coverage.
2. Golden fixtures для пропусков, отрицаний, противоречий, period/currency,
   pets/party и различия общей политики/ограниченного scope. Не использовать
   существование значения в legacy record как доказательство свойства.
3. Проверка изменений цены/источника, retirement/remap/delete и повторной
   подготовки proof на собственных изолированных fixtures. Без нагрузочных
   экспериментов и без старых audit/capacity DB.
4. Отдельные счётчики недостатка подтверждённых данных и отсутствия совпадений.
   Предложение freshness/retention правил и списка минимально нужных полей.

Результат первой части: воспроизводимая fixture-матрица и список реальных
пробелов, без заявления о качестве настоящего каталога. Нужный объём дальнейших
изменений определяет матрица, а не предположение о неполноте имеющегося кода.

## Зависимости для последующего настоящего прогона

До ingestion нужны согласованные источники/доступ, состав сохраняемых данных,
minimization/retention и отдельная изолированная конфигурация. Если для facts
выбирается LLM extraction, отдельно согласовать её payload/ключ/расходы;
разрешение на synthetic intent calls пункта 4 на объявления не распространяется.
Живой intent evaluator можно проверить позже на том же фиксированном corpus,
независимо от подготовки facts. Изменять его эталоны по результатам модели
ради повышения score нельзя.

## Offline инвентарь 1 ноября

Добавлены воспроизводимая source × field матрица, golden проверки отсутствующих
подтверждений и отдельный bounded PG прогон. Реальное coverage/freshness неизвестно;
пункт 5 не завершён. Конкретные пробелы, ограничения и предложение минимального
pilot payload/retention/freshness: [отчёт](../../reports/AI_FACT_QUALITY_OFFLINE_20261101.md).

## Counters и политики закрытого контура

Следующий offline шаг реализован: bounded quality audit, SQL freshness guard и
транзакционная очистка AI evidence с proof invalidation/reprepare. Production
автоматически не включается; global TTL нет. Полный контракт:
[policy](AI_FACT_QUALITY_POLICY_RU.md), [отчёт](../../reports/AI_FACT_QUALITY_NEXT_20261101.md).
Настоящий каталог по-прежнему не измерен; пункт 5 открыт.

## Приёмка согласованного Flatio pilot

1 ноября пользователь выбрал до 100 публичных Flatio records и согласовал
24h raw /30d cleaned evidence /24h price+availability /7d policy freshness.
Измерены 73 настоящие записи, 8 прошли eligibility/pipeline/proof. Пункт 5
выполнен в этом согласованном closed pilot scope; неподдерживаемые fields не
объявлены покрытыми, данные удалены. [Итог](../../reports/AI_FLATIO_PILOT_20261101.md).
Операционная/public интеграция относится к последующим этапам.

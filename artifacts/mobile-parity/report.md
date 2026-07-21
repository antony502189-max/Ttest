# 112233.es — mobile marketplace parity report

Дата проверки: 21 июля 2026

## Цель

Существующий frontend 112233.es перестроен под плотную mobile-first структуру референсов Idealista без замены проекта и без копирования чужого бренда или ассетов. Сохранены текущие данные, маршруты и бизнес-логика. Основная география всех поисковых и картографических сценариев — только Tenerife.

## Реализованная мобильная структура

- компактный белый header 112233.es;
- отдельное кликабельное продвигаемое объявление;
- отдельная lime-панель поиска с вкладками Vivienda/Turísticas;
- условия «Para quién», Tenerife location flow и magenta CTA Buscar;
- отдельная кнопка Publicar anuncio и блок Tus búsquedas;
- нижняя навигация Inicio / Búsquedas / Favoritos / Mensajes / Menú;
- полноэкранные location и filters flows, нижний sort sheet и Tenerife map flow;
- плотные карточки результатов и mobile detail с contact bar;
- app-like меню и frontend-only раздел сообщений;
- адаптация существующих профиля, публикации и служебных экранов;
- ES/EN/RU без смены маршрута;
- отсутствие горизонтального переполнения на обязательной responsive-матрице.

## Сохранённые бизнес-контракты

Поиск, URL-фильтры, сортировка, пагинация, Leaflet, markers, clusters, polygon search, favorites, saved searches, demo auth, owner isolation, IndexedDB media, профиль, Mis anuncios, публикация и редактирование, long-term/holiday режимы, контакты и существующая административная логика продолжают проходить исходный E2E-набор.

## Проверенные размеры

- мобильные: 360×800, 390×844, 412×915;
- tablet/desktop sanity: 768×1024, 1024×900, 1440×900;
- основной визуальный baseline: 390×844.

## Quality gates

- `npm run typecheck` — passed;
- `npm run lint` — passed;
- `npm run build` — passed;
- `npm run test:a11y` — 26 passed;
- `npm run test:visual` — 4 passed;
- `npm run test:e2e` — 89 passed.

Playwright timeout увеличен до 60 секунд, а итоговый набор закреплён на одном Chromium worker. Это устраняет конкуренцию browser storage, IndexedDB и внешних media-запросов. Отдельные проблемные сценарии и полный последовательный прогон завершились успешно.

В visual regression маскируется только растровое содержимое внешних Unsplash-фото; геометрия media-слотов, подписи, карточки и вся UI-композиция продолжают сравниваться. Финальные evidence-снимки содержат реальные фотографии.

## Визуальные артефакты

- `before/` — исходные контрольные скриншоты;
- `after/` — финальная responsive-матрица и основные состояния;
- `after/contact-sheet.png` — сводный лист ключевых mobile flows;
- `diff/` — композиции BEFORE / AFTER / DIFF для home, results, listing, location и map;
- `tests/visual-snapshots/chromium/` — versioned visual baselines для автоматической регрессии.

## Ограничения

Реализация остаётся frontend-only. География не расширялась за пределы Tenerife; backend, API, PWA, native apps, импорт и оплата не добавлялись.

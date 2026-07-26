# Контракт поведения

- Существующие экраны, карточки, фильтры и сортировки сохраняют baseline `19b3b8d`.
- Поддерживаются ровно ES, EN и RU.
- Карта, список и фильтры используют единые catalog, rental mode, query, filters, polygon, nearby coordinates, favorites и discarded state.
- URL, reload и Back не сбрасывают применимые параметры.
- Геолокация запрашивается только по явному действию.
- APK, API keys, `.env.local`, `node_modules`, test-results и emulator video не коммитятся.

## Геолокация

Типизированные результаты: `success`, `denied`, `unavailable`, `timeout`, `unsupported`, `outside`, `empty`. При success карта центрируется, показывает marker и сериализует `lat`, `lng`, `radio=30`, `cerca=1`. Ошибки не подменяются фиктивными координатами.

## Drawing

- До drawing CTA карта интерактивна.
- Freehand overlay существует только во время рисования.
- Polygon минимум из трёх точек фильтрует map/list и сохраняется в URL.
- После polygon видна `Buscar en esta zona` / `Search this area` / `Искать в этой области`.
- Cancel, redraw, delete, Back и reload проверяются отдельно.

## Guest/auth

- Favorite и hide доступны гостю в локальном scope.
- Contact и публикация гостя ведут в существующий auth flow.
- После demo-login профиль, сообщения, saved searches, публикация и owner CRUD используют user-scoped persistence.
- Post-auth Idealista APK не заявляется без фактического входа.

## Map fallback

Google Maps key и Map ID читаются только из environment. При config/auth/network failure остаётся доступный fallback. Headless Chromium может перейти с Vector на Raster Map; это ожидаемо и не подменяет проверки интерактивности.

# Инвентаризация экранов Idealista APK

Источник: переданный `app.apk`, реально установленный и запущенный в Android Emulator API 35.

- package: `com.idealista.android`
- version: `14.5.0`
- launcher: `.app.main.MainActivity`
- visual baseline: `19b3b8d3f3b29b8a39df686fe588c36faddb1592`
- main перед работой: `74afdf6ced0b4bc089ffca2bcac88dc426035223`

## До авторизации — фактически пройдено в эмуляторе

| Экран/состояние APK | Вход | Действия и состояния | Реализация 112233.es | Evidence |
|---|---|---|---|---|
| Первый запуск | clean install / relaunch | язык, continue | onboarding ES/EN/RU, reload | [launch](reference/apk-01-launch.png) |
| Страна и privacy | onboarding | España, privacy, skip login | España (Tenerife), privacy, skip | [launch](reference/apk-01-launch.png) |
| Главная | skip login | Vivienda, Turismo, жилец, место, поиск, публикация, tabs | mobile shell без редизайна | [home](reference/apk-06-home.png) |
| Выбор места | home → location | адрес; draw; map; nearby; phone; Back | четыре действия, `panel=ubicacion` | [location](reference/apk-08-location.png) |
| Рисование зоны | location → draw | интерактивная карта; draw/cancel/redraw/delete | freehand, URL polygon, reload | [drawing](reference/apk-10-draw-active.png) |
| Карта результатов | location/results → map | слои, позиция, список, фильтры, markers, clusters, preview | отдельная mobile Google Map | [web map](../../artifacts/true-target-parity/map.png) |
| Поиск рядом | location → nearby | Android permission, success/deny/error | permission по клику; все error states | [permission](reference/apk-27-nearby-dialog.png) |
| Поиск по телефону | location → phone | номер, тип операции/объекта, submit, Back | `panel=telefono`, точная карточка | [phone](reference/apk-24-phone.png) |
| Список результатов | search | cards, photos, favorite, hide, contact, filters, sort, map | URL-backed общий каталог | [web results](../../artifacts/true-target-parity/results.png) |
| Карточка объявления | list/map/phone | gallery, call/contact, favorite, hide/report/share | существующий route screen | Playwright |
| Нижняя навигация | основные экраны | Inicio, Búsquedas, Favoritos, Chat, Menú | реальные hash-routes | Playwright |
| Guest publication gate | home/menu → publish | login, Back | gate → `/acceso` | Playwright |
| Меню | tab Menú | account, publish, language, region, appearance/about | ES/EN/RU, реальные routes | [web menu](../../artifacts/true-target-parity/menu.png) |

System Back и browser Back проверены для onboarding, location, map/draw, phone, list, listing и auth gate. Прямые URL и reload проверены для location, list, map, polygon, nearby и phone.

## Авторизация и post-auth APK

Экран входа Idealista был открыт в реальном APK, но успешный вход не выполнялся: в пакете нет тестовой учётной записи Idealista, а создание внешнего аккаунта требует отдельного e-mail/подтверждения и не было разрешено. Персональные данные реальных пользователей не использовались.

Поэтому post-auth Idealista APK отмечен как **не подтверждён вручную**. Эквивалентные локальные потоки 112233.es проверены demo-аккаунтами:

| Поток сайта | Результат |
|---|---|
| login/error/logout/session reload | pass |
| registration/recovery/reset | pass |
| profile edit/avatar/account deletion | pass |
| favorites/saved searches/history/messages | pass, user-scoped |
| publication draft/validation/images/preview/finish | pass |
| own listings edit/status/renew/delete | pass |
| guest → auth → protected return route | pass |

## Языки

В APK подтверждены selector и переключение языка; детальный ручной guest-маршрут зафиксирован на испанском. На сайте каждый реализованный mobile state автоматически проверен на ES/EN/RU, включая динамические ошибки геолокации, кнопки, placeholder и aria-label. Browser auto-translate отключён через `notranslate`.

APK, UI dumps, test videos и временные emulator-файлы в git не добавлены.

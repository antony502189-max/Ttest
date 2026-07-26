# Визуальный контракт

Этот файл не вводит новый дизайн.

| Область | Источник | Правило |
|---|---|---|
| Существующие экраны | `19b3b8d` | размеры, цвета, spacing, typography, icons и geometry не менять |
| Existing filters/sort/cards/map | `19b3b8d` | состав и внешний вид не менять |
| Возвращённые location actions | Idealista APK 14.5.0 | существующий `m2-location-action` |
| Search this area | existing map CTA + APK behavior | не скрывать; локализовать; применять polygon |
| User marker | map convention | синий marker, белая обводка |
| Status/error | current mobile palette | success lime, error restrained red |

Изменены только два CSS-файла:

1. `src/freehand-map-drawing.css` — удалено правило PR43, скрывавшее рабочую Search this area через `display:none`.
2. `src/mobile-app-v2.css` — добавлены стили только для geo feedback, Search this area и current-location marker.

Visual snapshots не обновлялись.

# 112233.es

[Abrir la versión pública](https://antony502189-max.github.io/Ttest/)

Frontend completo de un marketplace de alquiler de habitaciones en Tenerife. La aplicación funciona íntegramente con datos mock y no necesita claves de API.

## Desarrollo

```bash
npm install
npm run dev
```

Todos los estados interactivos —búsqueda, filtros, mapa, favoritos, formularios, publicación y administración— funcionan en el cliente.

## Verificación

```bash
npm run lint
npm run typecheck
npm run build
```

Los scripts reproducibles de QA están en `scripts/`. Los artefactos locales de Playwright se guardan en `output/playwright/` y no se publican en Git.

## Stack

- React 19 + TypeScript
- Vite 8
- Tailwind CSS 4
- shadcn/ui + Radix UI
- React Router
- Lucide
- Playwright CLI + axe-core para QA

# 112233.es

[Abrir la versión pública](https://antony502189-max.github.io/Ttest/)

Frontend completo de un marketplace de alquiler de habitaciones en Tenerife. Los anuncios usan datos mock; los mapas se renderizan con Google Maps JavaScript API.

## Desarrollo

```bash
npm install
```

Crea `.env.local` a partir de `.env.example`:

```dotenv
VITE_GOOGLE_MAPS_API_KEY=
VITE_GOOGLE_MAPS_MAP_ID=
```

El Map ID es obligatorio en producción para Advanced Markers. El modo local puede usar temporalmente `DEMO_MAP_ID` cuando no se ha configurado uno propio. `.env.local` y el resto de archivos `.env.*` están ignorados por Git.

```bash
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
- Google Maps JavaScript API, Advanced Markers y MarkerClusterer
- Lucide
- Playwright CLI + axe-core para QA

# Карта навигации APK → Web

```text
onboarding
  └─ home
     ├─ location
     │  ├─ draw zone ──> map(draw) ──> Search this area ──> list
     │  ├─ search on map ──> map ──> marker ──> preview ──> listing
     │  ├─ nearby ──> permission ──> map(lat,lng,radius)
     │  └─ phone ──> phone form ──> matching listing
     ├─ search ──> list
     │  ├─ filters ──> list/map with the same state
     │  ├─ sort ──> list
     │  ├─ map ──> list / filters / marker preview
     │  └─ listing ──> favorite / hide / contact
     ├─ publish ──> guest gate ──> login ──> publication wizard
     └─ tabs ──> home / saved / favorites / messages / menu
```

| State | URL |
|---|---|
| location | `/#/?panel=ubicacion` |
| phone | `/#/?panel=telefono` |
| list | `/#/buscar?q=Tenerife&alquiler=long\|holiday` |
| map | `/#/buscar?...&vista=mapa` |
| draw entry | `/#/buscar?...&vista=mapa&dibujar=1` |
| polygon | `poligono=lat,lng;...` |
| nearby | `cerca=1&radio=30&lat=...&lng=...` |
| filters/sort | canonical params плюс `mobileOrden` |
| focused map listing | `anuncio=<listing-id>` |

На mobile монтируется только mobile implementation; скрытая desktop-карта больше не остаётся вторым источником состояния. От 768 px продолжает работать существующий route-based desktop UI baseline.

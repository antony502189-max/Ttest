# Frontend compression and cache baseline

## Baseline

The implementation branch starts from `63ca366ca97f51558b3db4e1778ef24938d474ad` (GitHub `main`). The original workspace's screenshot edits were not copied or changed.

Two anonymous production asset requests were captured on 2026-10-09 with
`Accept-Encoding: gzip`:

| Resource | Response | Transfer size | Cache policy |
| --- | --- | ---: | --- |
| Entry JavaScript | `application/javascript`, 200, no `Content-Encoding` | 776,075 B | `public, max-age=31536000, immutable` |
| Entry CSS | `text/css`, 200, no `Content-Encoding` | 369,607 B | `public, max-age=31536000, immutable` |

Together these critical text assets transferred 1,145,682 bytes without
compression. The live HTML response was 1,375 bytes and also had no
`Content-Encoding` or explicit `Cache-Control`. Production was not modified.
The prior Phase 1 report records the production release at
`a187918209d69a0a9fe1c5859634b0356d67ce87`; the application was not redeployed
for this task, so these live requests are a diagnostic snapshot rather than a
candidate before/after comparison.

The local production build of current `main` produced 776,075 B of entry JS and
369,729 B of entry CSS (1,145,804 B total). Served through the candidate Nginx
container and measured with `curl` body-byte counts, gzip level 5 transferred
254,951 B of JS and 66,376 B of CSS (321,327 B total), an exact 72.0% body-byte
reduction for these local HTTP/1.1 requests. This is not a browser timing
result or a claim about production HTTP/2/TLS transfer.

## Cache and compression policy

- HTML entry documents and stable public files revalidate with
  `Cache-Control: no-cache, must-revalidate`.
- Vite assets with the default eight-character filename hash under `/assets/`
  receive `public, max-age=31536000, immutable`.
- Stable URLs, including files below `/assets/` without the Vite hash pattern,
  do not receive immutable caching. Missing hashed files are not marked
  immutable.
- HTML, CSS, JavaScript, JSON build metadata, SVG, XML, and GeoJSON are gzip
  candidates. Already-compressed images and fonts are excluded.
- Proxied API routes explicitly disable Nginx gzip. The backend defaults to
  `no-store`, and API requests include bearer and refresh-token credentials;
  token-issuing responses also pass through those routes. Dynamic API
  compression is deferred until it can be scoped and reviewed per endpoint.
- No shared proxy cache was added. Private API and media visibility checks are
  unchanged.

## Verification

`scripts/test-nginx-static-delivery.sh` runs the exact pinned
`nginxinc/nginx-unprivileged:1.27-alpine` image against disposable fixtures. It
checks identity and gzip requests, valid decompression, `Vary`, content types,
compressed transfer semantics, hashed and stable asset cache headers, static
JSON/GeoJSON compression, API gzip bypass, security headers, 304 revalidation,
and uncached 404 behavior. `scripts/check-production-config.sh` invokes the
same runtime check and also runs `nginx -t` against the exact config.

The build, lint, typecheck, production dependency check, bundle security scan,
and pinned-image HTTP check passed locally. Browser visual baselines were not
rerun because the application source, CSS, and generated frontend assets are
unchanged; the production server config affects transfer encoding and caching
only. Cold/warm mobile FCP/LCP and first-photo timings remain unmeasured for
this PR and must not be inferred from the byte reduction.

No production containers, configuration, data, imports, or CDN settings were
changed.

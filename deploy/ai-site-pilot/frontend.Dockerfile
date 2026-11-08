ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG PILOT_SOURCE_SHA
COPY output/site-pilot-dist /usr/share/nginx/html/ai-pilot
COPY output/site-pilot-nginx.conf /etc/nginx/conf.d/default.conf
RUN test "${#PILOT_SOURCE_SHA}" -eq 40 && grep -F "\"source\": \"${PILOT_SOURCE_SHA}\"" /usr/share/nginx/html/ai-pilot/build-manifest.json && grep -F '"mode": "ai-site-pilot"' /usr/share/nginx/html/ai-pilot/build-manifest.json
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8443/health || exit 1

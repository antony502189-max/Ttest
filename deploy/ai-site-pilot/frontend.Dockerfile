ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY output/site-pilot-dist /usr/share/nginx/html/ai-pilot
COPY deploy/ai-site-pilot/nginx.conf /etc/nginx/conf.d/default.conf
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8443/health || exit 1

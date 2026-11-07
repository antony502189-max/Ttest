ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY output/private-demo-dist /usr/share/nginx/html
COPY deploy/ai-text-demo/nginx.conf /etc/nginx/conf.d/default.conf
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1:8443/ || exit 1

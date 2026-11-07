ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY output/private-demo-dist /usr/share/nginx/html
COPY deploy/ai-text-demo/nginx.conf /etc/nginx/conf.d/default.conf

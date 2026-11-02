ARG FRONTEND_BASE=ttest-main-audit-frontend:7d4c1255
FROM ${FRONTEND_BASE}
COPY --chmod=644 deploy/ai-text-lab/nginx.conf /etc/nginx/conf.d/default.conf
COPY --chmod=755 output/lab-dist/ /usr/share/nginx/html/
EXPOSE 8443
HEALTHCHECK NONE

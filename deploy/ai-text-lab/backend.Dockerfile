# Reuse installed dependencies only; ALL application code comes from this source.
ARG BACKEND_BASE=ttest-main-audit-backend:7d4c1255
FROM ${BACKEND_BASE}
USER root
WORKDIR /app
COPY --chown=app:app backend/ /app/
RUN chmod -R a+rX /app && mkdir -p /lab-tls && chown app:app /lab-tls
USER app
CMD ["uvicorn", "lab.ai_text:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]

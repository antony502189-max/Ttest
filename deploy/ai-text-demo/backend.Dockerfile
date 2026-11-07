ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY --chown=app:app backend/app /app/app
COPY --chown=app:app backend/alembic /app/alembic
COPY --chown=app:app backend/demo /app/demo
COPY --chown=app:app backend/alembic.ini /app/alembic.ini
CMD ["uvicorn", "demo.entry:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]

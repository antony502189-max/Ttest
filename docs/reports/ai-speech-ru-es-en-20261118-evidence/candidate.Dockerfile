FROM ttest-ai-local-housing:voice-en-parent-7b3fb581
LABEL io.opencontainers.image.revision="b88d7280b6acc6dfcb757bd973bb2e7ddf126c4f"
USER root
COPY --chown=999:999 backend/app /app/app
COPY --chown=999:999 backend/demo /app/demo
COPY --chown=999:999 backend/pilot /app/pilot
COPY --chown=999:999 backend/alembic /app/alembic
USER 999:999

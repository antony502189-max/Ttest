ARG BASE_IMAGE
FROM mirror.gcr.io/library/python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91 AS voice_assets
COPY deploy/ai-site-pilot/voice-requirements.txt /tmp/voice-requirements.txt
RUN python -m venv /opt/voice && /opt/voice/bin/pip install --no-cache-dir -r /tmp/voice-requirements.txt && /opt/voice/bin/pip check
COPY deploy/ai-site-pilot/prepare_voice_model.py /tmp/prepare_voice_model.py
RUN python /tmp/prepare_voice_model.py

FROM ${BASE_IMAGE}
COPY --from=voice_assets /opt/voice /opt/voice
COPY --from=voice_assets /opt/voice-model /opt/voice-model
COPY --chown=app:app backend/app /app/app
COPY --chown=app:app backend/alembic /app/alembic
COPY --chown=app:app backend/demo /app/demo
COPY --chown=app:app backend/pilot /app/pilot
COPY --chown=app:app backend/alembic.ini /app/alembic.ini
CMD ["uvicorn", "pilot.entry:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]

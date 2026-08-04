FROM python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home-dir /app app

COPY pyproject.toml constraints.txt ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
RUN pip install --constraint constraints.txt .
# Public-page rendering is optional at runtime, but the worker image must be
# capable of providing the configured Playwright fallback without a host browser.
RUN python -m playwright install --with-deps chromium

RUN mkdir -p /app/var/media /ms-playwright \
    && chown -R app:app /app /ms-playwright \
    && chmod -R a+rX /ms-playwright
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

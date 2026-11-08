FROM mirror.gcr.io/library/python:3.13-slim@sha256:6771159cd4fa5d9bba1258caf0b82e6b73458c694d178ad97c5e925c2d0e1a91
WORKDIR /app
COPY backend/ /app/
RUN pip install --no-cache-dir --constraint constraints.txt .
COPY backend/tests/pilot_proxy/server.py /app/proxy_fixture.py
COPY backend/tests/pilot_proxy/client.py /app/proxy_client.py
CMD ["uvicorn", "proxy_fixture:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log"]

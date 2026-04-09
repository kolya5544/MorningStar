FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
COPY docker-entrypoint.sh ./docker-entrypoint.sh

RUN chmod +x ./docker-entrypoint.sh \
    && useradd --create-home --shell /bin/sh appuser \
    && mkdir -p /data/object_storage \
    && chown -R appuser:appuser /app /data/object_storage

USER appuser

EXPOSE 8080

ENTRYPOINT ["./docker-entrypoint.sh"]

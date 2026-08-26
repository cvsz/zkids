# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN groupadd -r app && useradd -r -g app -m app
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

FROM base AS builder
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip wheel --wheel-dir /wheels -e . && pip wheel --wheel-dir /wheels Pillow PyYAML

FROM base AS runtime
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links=/wheels zkids Pillow PyYAML && rm -rf /wheels
COPY config ./config
COPY templates ./templates
COPY schemas ./schemas
RUN chown -R app:app /app && mkdir -p /data/episodes /data/logs && chown -R app:app /data
USER app
EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8010/api/health', timeout=3).read() else 1)"
ENV PYTHONPATH=/app/src
ENTRYPOINT ["python", "-m", "zkid.cli"]
CMD ["--help"]

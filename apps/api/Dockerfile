FROM python:3.12-slim-bookworm AS dependencies
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    git gcc libpq-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY requirements*.txt ./
ARG REQUIREMENTS_FILE=requirements-runtime.txt
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install -r "$REQUIREMENTS_FILE"

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH APP_HOME=/code \
    ENVIRONMENT=production NO_LM=TRUE NO_ENCODER=TRUE
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl ca-certificates && rm -rf /var/lib/apt/lists/* && \
    groupadd --gid 10001 ocl && useradd --uid 10001 --gid ocl --create-home ocl && \
    mkdir -p /code /temp /staticfiles /code/uploads && \
    chown -R ocl:ocl /code /temp /staticfiles
COPY --from=dependencies /opt/venv /opt/venv
WORKDIR /code
COPY --chown=ocl:ocl . .
ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="https://github.com/sihsalus/sihsalus-terminology" \
    org.opencontainers.image.revision=$SOURCE_COMMIT
USER ocl
RUN chmod +x set_build_version.sh release_version.sh wait_for_it.sh startup.sh \
    start_celery_worker.sh ping_celery_worker.sh start_celery_beat.sh && \
    ENVIRONMENT=ci python manage.py collectstatic --noinput && \
    ./set_build_version.sh
EXPOSE 8000
CMD ["bash", "./startup.sh"]

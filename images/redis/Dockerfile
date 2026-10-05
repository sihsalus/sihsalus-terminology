FROM redis:7.4-alpine@sha256:858f009f9709ce576febc734aa78b8f6d624b82571f9ddb6bda4377c833b3499
RUN apk upgrade --no-cache
ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="https://github.com/sihsalus/sihsalus-terminology" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}"

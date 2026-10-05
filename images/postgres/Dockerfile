FROM golang:1.27.1-alpine AS gosu
RUN apk add --no-cache git \
    && git clone --depth 1 --branch 1.19 https://github.com/tianon/gosu.git /src \
    && test "$(git -C /src rev-parse HEAD)" = 6456aaa0f3c854d199d0f037f068eb97515b7513
WORKDIR /src
RUN CGO_ENABLED=0 GOTOOLCHAIN=local go build -trimpath -ldflags='-s -w' -o /gosu .

FROM postgres:14.24-alpine@sha256:4ea9e5ed06591da7ea23eb65465e8d3187fe79f4d5ec3ae976d29a33b013e77a
RUN apk upgrade --no-cache
COPY --from=gosu /gosu /usr/local/bin/gosu
ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="https://github.com/sihsalus/sihsalus-terminology" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}"

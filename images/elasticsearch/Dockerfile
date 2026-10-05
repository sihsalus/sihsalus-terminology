FROM docker.elastic.co/elasticsearch/elasticsearch:8.19.22@sha256:e98f9c3b09beb2fbb9eaf667d602df3f0e00bd3644138b8458dc17ba1a675595
USER root
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
# Keep the supported server series and apply patch releases of its JSON libraries.
COPY jackson.sha256 /tmp/jackson.sha256
RUN set -eu; \
    cd /tmp; \
    for artifact in jackson-core jackson-databind; do \
      curl -fsSLO "https://repo.maven.apache.org/maven2/com/fasterxml/jackson/core/$artifact/2.21.7/$artifact-2.21.7.jar"; \
    done; \
    sha256sum -c jackson.sha256; \
    for artifact in jackson-core jackson-databind; do \
      find /usr/share/elasticsearch -type f -name "$artifact-2.21.6.jar" > /tmp/jackson-paths; \
      test -s /tmp/jackson-paths; \
      while IFS= read -r path; do \
        install -m 644 "$artifact-2.21.7.jar" "${path%2.21.6.jar}2.21.7.jar"; \
        rm "$path"; \
      done < /tmp/jackson-paths; \
    done; \
    rm /tmp/jackson-*.jar /tmp/jackson.sha256 /tmp/jackson-paths
USER 1000:0
ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="https://github.com/sihsalus/sihsalus-terminology" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}"

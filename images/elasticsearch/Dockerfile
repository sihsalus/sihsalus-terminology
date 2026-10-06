FROM docker.elastic.co/elasticsearch/elasticsearch:8.19.22@sha256:e98f9c3b09beb2fbb9eaf667d602df3f0e00bd3644138b8458dc17ba1a675595 AS upstream

FROM python:3.12-alpine AS jackson
WORKDIR /work
COPY --from=upstream /usr/share/elasticsearch/lib/elasticsearch-x-content-8.19.22.jar /patched/lib/elasticsearch-x-content-8.19.22.jar
COPY --from=upstream /usr/share/elasticsearch/lib/tools/plugin-cli/elasticsearch-x-content-8.19.22.jar /patched/lib/tools/plugin-cli/elasticsearch-x-content-8.19.22.jar
COPY jackson.sha256 patch-embedded-jackson.py /work/
RUN python patch-embedded-jackson.py

FROM upstream
USER root
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && rm /usr/share/elasticsearch/bin/elasticsearch-sql-cli /usr/share/elasticsearch/bin/elasticsearch-sql-cli-8.19.22.jar
# Keep the supported server series and apply patch releases of its JSON libraries.
COPY --from=jackson /patched/ /usr/share/elasticsearch/
COPY --from=jackson /work/jackson-core-2.21.7.jar /work/jackson-databind-2.21.7.jar /work/jackson.sha256 /tmp/
RUN set -eu; \
    cd /tmp; \
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
# Keep the attachment module on a checksum-verified upstream jsoup release.
ADD --checksum=sha256:e9d8c856856680427f096d156f02a414289985c930998fcb519ce5be39b42003 --chmod=644 \
    https://repo.maven.apache.org/maven2/org/jsoup/jsoup/1.23.2/jsoup-1.23.2.jar \
    /usr/share/elasticsearch/modules/ingest-attachment/jsoup-1.23.2.jar
RUN test -f /usr/share/elasticsearch/modules/ingest-attachment/jsoup-1.21.2.jar \
    && rm /usr/share/elasticsearch/modules/ingest-attachment/jsoup-1.21.2.jar
USER 1000:0
ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="https://github.com/sihsalus/sihsalus-terminology" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}"

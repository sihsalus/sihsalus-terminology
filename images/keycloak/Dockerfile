FROM quay.io/keycloak/keycloak:26.8.1@sha256:79c623a22abacf3fe6c00a5fb30f5b7843d717b234033b80995891c06116d244 AS builder
RUN /opt/keycloak/bin/kc.sh build --db=postgres --health-enabled=true --metrics-enabled=true \
    --http-relative-path=/auth --http-management-relative-path=/

FROM quay.io/keycloak/keycloak:26.8.1@sha256:79c623a22abacf3fe6c00a5fb30f5b7843d717b234033b80995891c06116d244
COPY --from=builder /opt/keycloak/ /opt/keycloak/
ENV KC_DB=postgres \
    KC_HEALTH_ENABLED=true \
    KC_METRICS_ENABLED=true \
    KC_CACHE=ispn \
    KC_HTTP_RELATIVE_PATH=/auth \
    KC_HTTP_MANAGEMENT_RELATIVE_PATH=/
# The management listener stays private; the application runs behind the HTTPS proxy.
HEALTHCHECK --interval=15s --timeout=5s --start-period=180s --retries=12 \
    CMD bash -ec "{ printf 'HEAD /health/ready HTTP/1.0\\r\\n\\r\\n' >&0; grep 'HTTP/1.0 200'; } 0<>/dev/tcp/localhost/9000"
ARG SOURCE_COMMIT
LABEL org.opencontainers.image.source="https://github.com/sihsalus/sihsalus-terminology" \
      org.opencontainers.image.revision="${SOURCE_COMMIT}"
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
CMD ["start", "--optimized"]

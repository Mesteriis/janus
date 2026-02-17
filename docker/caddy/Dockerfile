# syntax=docker/dockerfile:1.7
ARG CADDY_VERSION=2.10.2

FROM caddy:${CADDY_VERSION}-builder AS builder

ENV GOTOOLCHAIN=go1.25.1

# ВАЖНО: кэшируем /go/pkg/mod (модули) и /root/.cache/go-build (кэш компиляции)
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    xcaddy build \
      --with github.com/mholt/caddy-l4@8e3b9724e26abc5f028fbce9948682bc62864804 \
      --with github.com/greenpau/caddy-security@v1.1.29 \
      --with github.com/mholt/caddy-ratelimit \
      --with github.com/darkweak/souin/plugins/caddy \
      --with github.com/caddyserver/cache-handler \
      --with github.com/greenpau/caddy-trace \
      --with github.com/grom11/caddy-logtail \
      --with github.com/lucaslorentz/caddy-docker-proxy/v2 \
      --with github.com/caddyserver/geoip2 \
      --with github.com/ss098/caddy-extauth \
      --with github.com/caddy-dns/cloudflare \
      --with github.com/gamalan/caddy-tlsredis \
      --with github.com/caddyserver/replace-response \
      --with github.com/caddyserver/json5-adapter \
      --with github.com/caddyserver/caddy-fs-s3 \
      --with github.com/caddyserver/s3storage \
      --with github.com/mholt/caddy-webdav

FROM caddy:${CADDY_VERSION}
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
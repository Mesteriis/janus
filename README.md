# ct-112-tunel-new

Caddy + Dashboard (FastAPI + Vue 3) для управления маршрутами. Cloudflare Tunnel работает в режиме catch‑all:
весь HTTP/HTTPS трафик по доменам и поддоменам направляется на Caddy, а исключения (например SSH) задаются отдельно.

## Требования
- Docker + Docker Compose
- Свободные порты `80`, `443`, `8090`
- Доступ к Cloudflare Zero Trust (Tunnel + API token)

## Быстрый старт
```bash
cd /Users/avm/projects/Personal/infra/ct-112-tunel-new

# 1) заполнить .env (см. шаблон)
cp .env.example .env

# 2) старт
docker compose up -d --build
```

Dashboard будет доступен по `http://localhost:8090`.

## Cloudflare Tunnel (catch‑all)
Идея: **не добавляем домены по одному**. В Cloudflare Tunnel есть fallback‑правило, которое отправляет весь
HTTP/HTTPS трафик на Caddy. Hostnames нужны только для исключений.

### Настройка
1. В Cloudflare Zero Trust создайте tunnel и скопируйте **Tunnel Token**.
2. Создайте API token с правами на управление tunnel конфигурацией.
3. Заполните `.env` (см. `.env.example`).
4. Поднимите сервисы:
   ```bash
   docker compose up -d cloudflared dashboard
   ```
5. В dashboard нажмите **«Применить»** (отправит конфигурацию в Cloudflare).

### DNS
Для домена и wildcard создайте DNS записи в Cloudflare, указывающие на tunnel.
Минимум:
- `example.com` (apex)
- `*.example.com`

### SSH исключение (22 порт)
Cloudflare Tunnel связывает один hostname с одним сервисом, поэтому SSH нужен отдельный hostname,
например `ssh.example.com`.

В dashboard добавьте исключение:
- `Hostname`: `ssh.example.com`
- `Service`: `ssh://<git-host>:22`
- `Enabled`: `true`

Нажмите **«Применить»**.

## Маршруты Caddy
Dashboard управляет `routes.json` и генерирует `config.json5` (JSON5-конфиг Caddy). Caddyfile больше не используется.

- Источник правды: `caddy/routes.json`
- Генерируемый файл: `caddy/config.json5`

### Добавление маршрута
1. Откройте dashboard.
2. Заполните домены и upstream.
3. Нажмите **«Создать маршрут»**.

### Wildcard
- Включите «Авто‑wildcard» или укажите домен с `*.`.

### Временное отключение
- На карточке маршрута нажмите **«Отключить»**.

## Файлы и окружение
- `DASHBOARD_PORT` — порт dashboard (по умолчанию `8090`).
- `CADDY_EMAIL` — email для ACME.
- `ROUTES_FILE` и `CADDY_CONFIG` — пути к конфигурациям.
- `CLOUDFLARE_TUNNEL_TOKEN` — токен для `cloudflared` в режиме `--token`.
- `CLOUDFLARE_API_TOKEN` — API token для управления tunnel.
- `CLOUDFLARE_DEFAULT_SERVICE` — куда направлять fallback (catch‑all).
- `CLOUDFLARE_HOSTNAMES_FILE` — файл с публичными hostnames.
- `CLOUDFLARE_STATE_FILE` — файл состояния CF (token + tunnels).
- `CF_API_TOKEN` — токен для dns-01 в Caddy (если используете ACME через Cloudflare).

## Docker Desktop (macOS/Windows)
Файл `docker-compose.override.yaml` переводит сервисы на bridge‑сеть и пробрасывает порты
`80`, `443`, `8090` на хост.

Значение по умолчанию для fallback:
- Docker Desktop: `CLOUDFLARE_DEFAULT_SERVICE=http://caddy:80`
- Linux host‑сеть: `CLOUDFLARE_DEFAULT_SERVICE=http://127.0.0.1:80`

## Кастомный Caddy с плагинами
Собирается через `caddy/Dockerfile` (xcaddy) и используется в `docker-compose.yaml` вместо vanilla образа.
Плагины в сборке:
- layer4, docker-proxy, realip, geoip2
- reverse proxy утилиты: replace-response, cache-handler, souin, json5-adapter
- security stack: caddy-security, caddy-security-appsec, caddy-ratelimit, crowdsec-bouncer (оба варианта), extauth
- storage/fs: caddy-fs-s3, s3storage, tlsredis
- observability: prometheus, trace, logtail
- dns/acme: cloudflare dns provider
- webdav utility

Сборка/обновление образа:
```bash
docker compose build caddy
docker compose up -d caddy
```

Примеры включения функционала в `caddy/config.json5` (структура JSON/JSON5):
- Метрики/trace:
```
{
  "handle": [
    { "handler": "prometheus" },
    { "handler": "trace", "exporter": { "otel_endpoint": "http://otel-collector:4318" } }
  ]
}
```
- L4 (SSH) через layer4:
```
see layer4 docs; config собирается через XCADDY-плагин l4 (пример остался в истории Caddyfile).
```

Примечание: docker-proxy пригодится на внешних Docker хостах (labels). crowdsec/appsec/geoip2 требуют собственных конфигов и данных (LAPI URL, mmdb). dynamicdns не включён; добавляйте опционально через xcaddy, если потребуется.
Для tlsredis требуется сервис redis (добавлен в compose). GeoIP база ожидается в `./geoip/GeoLite2-City.mmdb` (volume в compose).

## Полезные команды
```bash
# Старт/пересборка
docker compose up -d --build

# Логи
docker compose logs -f caddy
docker compose logs -f dashboard
docker compose logs -f cloudflared

# Остановка
docker compose down
```

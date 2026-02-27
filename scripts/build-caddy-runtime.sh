#!/usr/bin/env bash
set -euo pipefail

# Скрипт сборки образа janus/caddy-runtime:local
# Использование: ./scripts/build-caddy-runtime.sh [addons...]
# Пример: ./scripts/build-caddy-runtime.sh cloudflare_dns realip rate_limit

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$PROJECT_DIR/docker/caddy-runtime"
IMAGE_NAME="${CADDY_RUNTIME_IMAGE:-janus/caddy-runtime:local}"

# Аддоны по умолчанию (безопасный минимум для Cloudflare + reverse proxy)
DEFAULT_ADDONS=("cloudflare_dns" "realip")

# Карта аддонов -> модули
declare -A ADDON_MODULES=(
    ["cloudflare_dns"]="github.com/caddy-dns/cloudflare"
    ["realip"]="github.com/captncraig/caddy-realip"
    ["cache_handler"]="github.com/caddyserver/cache-handler"
    ["replace_response"]="github.com/caddyserver/replace-response"
    ["rate_limit"]="github.com/mholt/caddy-ratelimit"
)

# Парсинг аргументов
ADDONS=()
if [[ $# -gt 0 ]]; then
    ADDONS=("$@")
else
    ADDONS=("${DEFAULT_ADDONS[@]}")
fi

echo "🔨 Сборка образа: $IMAGE_NAME"
echo "📦 Аддоны: ${ADDONS[*]}"
echo ""

# Создание директории сборки
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Генерация Dockerfile
{
    echo "FROM caddy:2-builder AS builder"
    echo "RUN xcaddy build \\"
    
    MODULES=()
    for addon in "${ADDONS[@]}"; do
        if [[ -n "${ADDON_MODULES[$addon]:-}" ]]; then
            MODULES+=("${ADDON_MODULES[$addon]}")
        else
            echo "⚠️  Неизвестный аддон: $addon (пропускаем)" >&2
        fi
    done
    
    for i in "${!MODULES[@]}"; do
        if [[ $i -eq $((${#MODULES[@]} - 1)) ]]; then
            echo "  --with ${MODULES[$i]}"
        else
            echo "  --with ${MODULES[$i]} \\"
        fi
    done
    
    echo ""
    echo "FROM caddy:2"
    echo "COPY --from=builder /usr/bin/caddy /usr/bin/caddy"
} > "$BUILD_DIR/Dockerfile"

echo "📄 Dockerfile:"
cat "$BUILD_DIR/Dockerfile"
echo ""

# Генерация Caddyfile для runtime (без auto HTTPS, для Cloudflare Tunnel)
{
    echo "# Caddyfile для Cloudflare Tunnel (без HTTPS redirect)"
    echo "# Трафик от Tunnel уже зашифрован, TLS terminates на edge Cloudflare"
    echo ""
    echo "{"
    echo "    # Не делаем HTTPS redirect — Cloudflare Tunnel отправляет HTTP"
    echo "    auto_https off"
    echo "}"
    echo ""
    echo "# Catch-all для необработанных запросов"
    echo ":80 {"
    echo "    respond \"Janus Caddy Runtime - No route configured\" 200"
    echo "}"
} > "$BUILD_DIR/Caddyfile"

echo "📄 Caddyfile (для Tunnel):"
cat "$BUILD_DIR/Caddyfile"
echo ""

# Сборка образа
echo "🚀 Запуск сборки..."
docker build \
    --tag "$IMAGE_NAME" \
    --file "$BUILD_DIR/Dockerfile" \
    "$BUILD_DIR"

echo ""
echo "✅ Образ собран: $IMAGE_NAME"
echo ""

# Проверка образа
echo "📊 Информация об образе:"
docker image inspect "$IMAGE_NAME" --format='ID: {{.Id}}
Создан: {{.Created}}
Размер: {{.Size}} байт'

echo ""
echo "🎉 Готово!"
echo ""
echo "📋 Следующие шаги:"
echo "   1. Проверь что /var/run/docker.sock доступен в контейнере"
echo "   2. Запусти: docker compose up -d"
echo "   3. Смотри логи: docker compose logs -f dashboard"

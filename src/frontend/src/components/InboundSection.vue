<template>
  <section class="cloudflare inbound">
    <div class="section-header">
      <h2>Источники входящих соединений</h2>
    </div>

    <div v-if="availableSources.length > 1" class="inbound-tabs" role="tablist" aria-label="Источники">
      <button
        v-if="tunnelEnabled"
        class="ghost"
        type="button"
        :class="{ active: activeSource === 'cloudflare' }"
        @click="activeSource = 'cloudflare'"
      >
        Cloudflare Tunnel
      </button>
      <button
        v-if="vpnEnabled"
        class="ghost"
        type="button"
        :class="{ active: activeSource === 'vpn' }"
        @click="activeSource = 'vpn'"
      >
        VPN
      </button>
    </div>

    <div v-if="activeSource === 'cloudflare' && tunnelEnabled" class="cloudflare-stack">
      <div class="inbound-toolbar">
        <button class="ghost key-toggle" type="button" @click="tokenPanelOpen = !tokenPanelOpen" :disabled="saving">
          <span aria-hidden="true">Key</span>
          <span>{{ tokenPanelOpen ? 'Скрыть токен' : 'Токен Cloudflare' }}</span>
        </button>
        <button class="ghost" type="button" @click="$emit('refresh')" :disabled="loading || saving">Обновить</button>
      </div>

      <div v-if="tokenPanelOpen" class="panel token-panel">
        <h3>Cloudflare API Token</h3>
        <div class="field">
          <label for="cf-api-token">Token</label>
          <input id="cf-api-token" v-model="tokenInput" type="password" :placeholder="tokenPlaceholder" autocomplete="off" />
          <small>Токен сохраняется в файл: <code>{{ cloudflare.token_file }}</code></small>
        </div>
        <div class="route-actions">
          <button class="primary" type="button" @click="saveToken" :disabled="saving">Сохранить токен</button>
          <button class="ghost" type="button" @click="$emit('clear-token')" :disabled="saving || !cloudflare.token_present">Очистить</button>
        </div>
        <small v-if="!cloudflare.token_present">
          Токен не найден. Сгенерируйте его:
          <a :href="cloudflare.token_generation_url" target="_blank" rel="noreferrer">Cloudflare API Tokens</a>
        </small>
        <small v-else>
          Источник токена: <strong>{{ cloudflare.token_source }}</strong>
        </small>
      </div>

      <div class="panel tunnels-panel">
        <h3>Сгенерированные туннели</h3>
        <div v-if="loading" class="empty">Загружаем туннели...</div>
        <div v-else-if="!cloudflare.tunnels?.length" class="empty">Туннели не найдены.</div>
        <div v-else class="routes-grid">
          <article v-for="tunnel in cloudflare.tunnels" :key="tunnel.id" class="route-card">
            <div class="route-header">
              <div>
                <p class="route-title">{{ tunnel.name }}</p>
                <p class="route-upstream">{{ tunnel.id }}</p>
              </div>
              <span class="badge enabled">{{ tunnel.status || 'unknown' }}</span>
            </div>
            <div class="route-meta">
              <span class="tag">{{ tunnel.account_name }}</span>
              <span v-if="tunnel.created_at" class="tag">{{ formatDate(tunnel.created_at) }}</span>
              <span v-if="tunnel.container_name" class="tag">{{ tunnel.container_name }}</span>
            </div>
            <div class="field">
              <label>Домены</label>
              <div v-if="tunnel.domains?.length" class="route-meta">
                <span v-for="domain in tunnel.domains" :key="domain" class="tag">{{ domain }}</span>
              </div>
              <small v-else>Нет привязанных доменов.</small>
            </div>
            <div class="route-actions">
              <button
                v-if="(tunnel.status || '').toLowerCase() === 'inactive'"
                class="primary"
                type="button"
                :disabled="loading || saving"
                @click="$emit('start-tunnel', tunnel)"
              >
                Запустить
              </button>
              <button
                class="ghost danger"
                type="button"
                :disabled="loading || saving"
                @click="$emit('delete-tunnel', tunnel)"
              >
                Удалить контейнер
              </button>
            </div>
          </article>
        </div>
      </div>
    </div>

    <div v-else-if="activeSource === 'vpn' && vpnEnabled" class="vpn-stack">
      <div class="inbound-tabs" role="tablist" aria-label="VPN режим">
        <button class="ghost" type="button" :class="{ active: vpnMode === 'server' }" @click="vpnMode = 'server'">
          VPN Server
        </button>
        <button class="ghost" type="button" :class="{ active: vpnMode === 'client' }" @click="vpnMode = 'client'">
          VPN Client
        </button>
      </div>

      <template v-if="vpnMode === 'server'">
        <div v-if="!vpn.servers?.length" class="panel">
          <h3>WireGuard VPN</h3>
          <p class="subtitle">VPN серверы еще не созданы.</p>
          <div class="row">
            <input v-model="vpnServerName" type="text" placeholder="Имя сервера (необязательно)" />
            <button class="primary" type="button" :disabled="loading || saving" @click="requestCreateServer">Поднять VPN Server</button>
          </div>
        </div>

        <template v-else>
          <div class="panel">
            <div class="section-header">
              <h3>WireGuard серверы</h3>
              <button class="primary" type="button" :disabled="loading || saving" @click="requestCreateServer">Добавить еще VPN Server</button>
            </div>
            <small>Все данные сохраняются в: <code>{{ vpn.data_dir }}</code></small>
          </div>

          <div class="routes-grid">
            <article v-for="server in vpn.servers" :key="server.id" class="route-card">
              <div class="route-header">
                <div>
                  <p class="route-title">{{ server.name }}</p>
                  <p class="route-upstream">{{ server.id }}</p>
                </div>
                <span class="badge" :class="server.running ? 'enabled' : 'disabled'">{{ server.running ? 'running' : 'stopped' }}</span>
              </div>
              <div class="route-meta">
                <span class="tag">UDP {{ server.listen_port }}</span>
                <span class="tag">{{ server.subnet_cidr }}</span>
                <span class="tag">{{ server.endpoint }}</span>
              </div>
              <div class="route-meta">
                <span class="tag">{{ server.container_name }}</span>
                <span class="tag">{{ server.server_public_key }}</span>
              </div>
              <div class="route-actions">
                <button
                  v-if="!server.running"
                  class="primary"
                  type="button"
                  :disabled="loading || saving"
                  @click="$emit('start-vpn-server', server.id)"
                >
                  Запустить
                </button>
                <button
                  v-else
                  class="ghost"
                  type="button"
                  :disabled="loading || saving"
                  @click="$emit('stop-vpn-server', server.id)"
                >
                  Остановить
                </button>
                <button class="ghost danger" type="button" :disabled="loading || saving" @click="$emit('delete-vpn-server', server.id)">
                  Удалить сервер
                </button>
              </div>

              <div class="field">
                <label>Добавить клиент</label>
                <div class="row">
                  <input v-model="vpnClientNames[server.id]" type="text" placeholder="Имя клиента (необязательно)" />
                  <button class="ghost" type="button" :disabled="loading || saving" @click="requestAddClient(server.id)">Добавить</button>
                </div>
              </div>

              <div class="field">
                <label>Клиенты</label>
                <div v-if="server.clients?.length" class="overrides-list">
                  <div v-for="client in server.clients" :key="client.id" class="override-item slim">
                    <div class="route-meta">
                      <span class="tag">{{ client.name }}</span>
                      <span class="tag">{{ client.address }}</span>
                    </div>
                    <div class="route-actions">
                      <button
                        class="ghost"
                        type="button"
                        :disabled="loading || saving"
                        @click="$emit('show-vpn-client-config', server.id, client.id)"
                      >
                        Конфиг
                      </button>
                    </div>
                  </div>
                </div>
                <small v-else>Клиенты не добавлены.</small>
              </div>

              <small>{{ server.instructions }}</small>
            </article>
          </div>
        </template>
      </template>

      <template v-else>
        <div class="panel">
          <div class="section-header">
            <h3>WireGuard клиентские подключения</h3>
          </div>
          <small>Трафик из VPN-интерфейса автоматически перенаправляется на локальный Caddy (:80).</small>
        </div>

        <div class="panel">
          <h3>Добавить подключение</h3>
          <div class="row">
            <input v-model="vpnLinkName" type="text" placeholder="Имя подключения (необязательно)" />
          </div>
          <div class="field">
            <label>WireGuard client config</label>
            <textarea v-model="vpnLinkConfigText" rows="10" spellcheck="false" placeholder="[Interface] ... [Peer] ..."></textarea>
          </div>
          <div class="route-actions">
            <button class="primary" type="button" :disabled="loading || saving" @click="requestCreateLink">Подключить VPN</button>
          </div>
        </div>

        <div class="panel">
          <h3>Подключения</h3>
          <div v-if="!vpn.links?.length" class="empty">Подключения не созданы.</div>
          <div v-else class="routes-grid">
            <article v-for="link in vpn.links" :key="link.id" class="route-card">
              <div class="route-header">
                <div>
                  <p class="route-title">{{ link.name }}</p>
                  <p class="route-upstream">{{ link.id }}</p>
                </div>
                <span class="badge" :class="link.running ? 'enabled' : 'disabled'">{{ link.running ? 'running' : 'stopped' }}</span>
              </div>
              <div class="route-meta">
                <span class="tag">{{ link.interface }}</span>
                <span class="tag">{{ link.container_name }}</span>
              </div>
              <div class="route-actions">
                <button
                  v-if="!link.running"
                  class="primary"
                  type="button"
                  :disabled="loading || saving"
                  @click="$emit('start-vpn-link', link.id)"
                >
                  Запустить
                </button>
                <button
                  v-else
                  class="ghost"
                  type="button"
                  :disabled="loading || saving"
                  @click="$emit('stop-vpn-link', link.id)"
                >
                  Остановить
                </button>
                <button class="ghost" type="button" :disabled="loading || saving" @click="$emit('show-vpn-link-config', link.id)">
                  Конфиг
                </button>
                <button class="ghost danger" type="button" :disabled="loading || saving" @click="$emit('delete-vpn-link', link.id)">
                  Удалить
                </button>
              </div>
              <small>{{ link.instructions }}</small>
            </article>
          </div>
        </div>
      </template>
    </div>
    <div v-else class="panel">
      <p class="subtitle">Входящие источники отключены в настройках.</p>
    </div>

    <div v-if="vpnEnabled && vpnClientConfig.open" class="modal-backdrop" @click.self="$emit('close-vpn-client-config')">
      <div class="modal modal-large">
        <h3>{{ vpnClientConfig.title || 'WireGuard client config' }}</h3>
        <textarea :value="vpnClientConfig.text" rows="16" readonly spellcheck="false"></textarea>
        <div class="modal-actions">
          <button class="ghost" type="button" @click="$emit('close-vpn-client-config')">Закрыть</button>
        </div>
      </div>
    </div>

    <div v-if="vpnEnabled && vpnLinkConfig.open" class="modal-backdrop" @click.self="$emit('close-vpn-link-config')">
      <div class="modal modal-large">
        <h3>{{ vpnLinkConfig.title || 'WireGuard link config' }}</h3>
        <textarea :value="vpnLinkConfig.text" rows="16" readonly spellcheck="false"></textarea>
        <div class="modal-actions">
          <button class="ghost" type="button" @click="$emit('close-vpn-link-config')">Закрыть</button>
        </div>
      </div>
    </div>

    <p class="error">{{ error }}</p>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  cloudflare: {
    type: Object,
    required: true,
  },
  vpn: {
    type: Object,
    required: true,
  },
  tunnelEnabled: {
    type: Boolean,
    default: true,
  },
  vpnEnabled: {
    type: Boolean,
    default: true,
  },
  vpnClientConfig: {
    type: Object,
    default: () => ({ open: false, text: '', title: '' }),
  },
  vpnLinkConfig: {
    type: Object,
    default: () => ({ open: false, text: '', title: '' }),
  },
  loading: {
    type: Boolean,
    default: false,
  },
  saving: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits([
  'refresh',
  'save-token',
  'clear-token',
  'delete-tunnel',
  'start-tunnel',
  'create-vpn-server',
  'start-vpn-server',
  'stop-vpn-server',
  'delete-vpn-server',
  'add-vpn-client',
  'show-vpn-client-config',
  'close-vpn-client-config',
  'create-vpn-link',
  'start-vpn-link',
  'stop-vpn-link',
  'delete-vpn-link',
  'show-vpn-link-config',
  'close-vpn-link-config',
])

const activeSource = ref('cloudflare')
const vpnMode = ref('server')
const tokenPanelOpen = ref(false)
const tokenInput = ref('')
const vpnServerName = ref('')
const vpnClientNames = ref({})
const vpnLinkName = ref('')
const vpnLinkConfigText = ref('')

const tokenPlaceholder = computed(() =>
  tokenInput.value ? 'Обновление токена' : 'Вставьте Cloudflare API token'
)
const availableSources = computed(() => {
  const result = []
  if (props.tunnelEnabled) result.push('cloudflare')
  if (props.vpnEnabled) result.push('vpn')
  return result
})

watch(
  availableSources,
  (sources) => {
    if (!sources.includes(activeSource.value)) {
      activeSource.value = sources[0] || 'cloudflare'
    }
  },
  { immediate: true }
)

function saveToken() {
  emit('save-token', tokenInput.value, () => {
    tokenInput.value = ''
  })
}

function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ru-RU')
}

function requestCreateServer() {
  emit('create-vpn-server', vpnServerName.value)
  vpnServerName.value = ''
}

function requestAddClient(serverId) {
  const name = vpnClientNames.value[serverId] || ''
  emit('add-vpn-client', serverId, name)
  vpnClientNames.value[serverId] = ''
}

function requestCreateLink() {
  emit('create-vpn-link', vpnLinkName.value, vpnLinkConfigText.value)
  vpnLinkName.value = ''
  vpnLinkConfigText.value = ''
}
</script>

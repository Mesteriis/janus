<template>
  <section class="panel caddy-runtime">
    <div class="section-header">
      <div>
        <h2>Caddy Runtime</h2>
        <p class="subtitle">Сборка контейнера Caddy с выбранными аддонами, автоподъём и мониторинг.</p>
      </div>
      <div class="route-actions">
        <button class="ghost" type="button" @click="refreshAll" :disabled="busy">Обновить</button>
        <button class="ghost" type="button" @click="loadDefaultCaddyfile" :disabled="busy">Стандартный Caddyfile</button>
      </div>
    </div>

    <div class="route-meta">
      <span class="tag">State: {{ status.state || 'unknown' }}</span>
      <span class="tag">Container: {{ status.container?.container_name || '-' }}</span>
      <span class="tag">Health: {{ status.container?.health || 'unknown' }}</span>
      <span class="tag">Monitor: {{ status.monitor?.enabled ? 'on' : 'off' }}</span>
      <span v-if="status.install?.build_id" class="tag">Build: {{ status.install.build_id }}</span>
      <span class="tag">Live: {{ streamConnected ? 'SSE' : 'polling' }}</span>
    </div>

    <div v-if="status.install?.in_progress" class="field">
      <label>Сборка и установка</label>
      <div class="progress-wrap">
        <div class="progress-bar" :style="{ width: `${installProgress}%` }"></div>
      </div>
      <small>{{ status.install?.step || 'build' }} · {{ installProgress }}%</small>
    </div>

    <div v-if="status.state === 'not_installed'" class="panel subtle">
      <h3>Контейнер Caddy не найден</h3>
      <p class="subtitle">Выберите аддоны и нажмите установку.</p>

      <div class="field">
        <label>Пресеты</label>
        <div class="route-actions">
          <button
            v-for="(preset, key) in presets"
            :key="key"
            class="ghost"
            type="button"
            :disabled="busy"
            @click="applyPreset(key)"
          >
            {{ preset.label }}
          </button>
        </div>
      </div>

      <div class="field">
        <label>Аддоны</label>
        <div class="addons-grid">
          <label v-for="(addon, key) in addons" :key="key" class="addon-item">
            <input v-model="selectedAddons" type="checkbox" :value="key" :disabled="busy" />
            <span>
              <strong>{{ addon.label }}</strong>
              <small>{{ addon.description }}</small>
            </span>
          </label>
        </div>
      </div>

      <div class="route-actions">
        <button class="primary" type="button" :disabled="busy" @click="install(false)">Установить Caddy</button>
      </div>
    </div>

    <div v-else class="panel subtle">
      <div class="section-header">
        <h3>Управление контейнером</h3>
        <div class="route-actions">
          <button class="primary" type="button" :disabled="busy || status.install?.in_progress" @click="startContainer">Запустить</button>
          <button class="ghost" type="button" :disabled="busy || status.install?.in_progress" @click="stopContainer">Остановить</button>
          <button class="ghost" type="button" :disabled="busy || status.install?.in_progress" @click="install(true)">Переустановить</button>
          <button class="ghost" type="button" :disabled="busy || status.install?.in_progress || !status.profiles?.length" @click="rollback()">Rollback</button>
        </div>
      </div>
      <small>При падении контейнера watchdog попробует поднять его автоматически.</small>
    </div>

    <div class="panel subtle">
      <div class="section-header">
        <h3>Логи</h3>
        <div class="route-actions">
          <button class="ghost" type="button" :class="{ active: logSource === 'all' }" @click="setLogSource('all')">Все</button>
          <button class="ghost" type="button" :class="{ active: logSource === 'build' }" @click="setLogSource('build')">Build</button>
          <button class="ghost" type="button" :class="{ active: logSource === 'runtime' }" @click="setLogSource('runtime')">Runtime</button>
          <button class="ghost" type="button" :class="{ active: logSource === 'monitor' }" @click="setLogSource('monitor')">Monitor</button>
        </div>
      </div>
      <textarea :value="renderedLogs" rows="16" readonly spellcheck="false"></textarea>
    </div>

    <div class="panel subtle">
      <h3>История операций</h3>
      <div v-if="status.profiles?.length" class="row">
        <select v-model="rollbackBuildId">
          <option value="">Авто (предыдущий успешный)</option>
          <option v-for="profile in status.profiles" :key="profile.build_id" :value="profile.build_id">
            {{ profile.build_id }} · {{ (profile.addons || []).join(', ') || 'no addons' }}
          </option>
        </select>
      </div>
      <div v-if="!status.history?.length" class="empty">Операций пока нет.</div>
      <div v-else class="overrides-list">
        <div v-for="entry in status.history" :key="`${entry.ts}-${entry.action}`" class="override-item slim">
          <div class="route-meta">
            <span class="tag">{{ entry.action }}</span>
            <span class="tag">{{ entry.success ? 'ok' : 'error' }}</span>
            <span class="tag">{{ formatTs(entry.ts) }}</span>
          </div>
          <small>{{ entry.message }}</small>
        </div>
      </div>
    </div>

    <p class="error">{{ error }}</p>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { apiGet, apiPost } from '../services/api.js'

const status = ref({
  state: 'not_installed',
  container: {},
  install: { in_progress: false, progress: 0, step: 'idle' },
  available_addons: {},
  presets: {},
  history: [],
  monitor: {},
})

const addons = computed(() => status.value.available_addons || {})
const presets = computed(() => status.value.presets || {})
const installProgress = computed(() => Number(status.value.install?.progress || 0))

const selectedAddons = ref([])
const busy = ref(false)
const error = ref('')
const logs = ref([])
const logSource = ref('all')
const streamConnected = ref(false)
const rollbackBuildId = ref('')
let timer = null
let stream = null

const renderedLogs = computed(() => {
  if (!logs.value.length) return ''
  return logs.value
    .map((line) => `[${line.ts || '-'}] [${line.source || 'system'}] ${line.message || ''}`)
    .join('\n')
})

function formatTs(ts) {
  if (!ts) return ''
  try {
    return new Date(ts).toLocaleString()
  } catch {
    return ts
  }
}

function applyPreset(key) {
  const preset = presets.value?.[key]
  selectedAddons.value = Array.isArray(preset?.addons) ? [...preset.addons] : []
}

async function loadStatus() {
  const data = await apiGet('/api/caddy/runtime/status')
  status.value = data || status.value
  if (!selectedAddons.value.length && Array.isArray(data?.selected_addons)) {
    selectedAddons.value = [...data.selected_addons]
  }
}

async function loadLogs() {
  const data = await apiGet(`/api/caddy/runtime/logs?source=${encodeURIComponent(logSource.value)}&limit=220`)
  logs.value = Array.isArray(data?.entries) ? data.entries : []
}

function closeStream() {
  if (stream) {
    stream.close()
    stream = null
  }
  streamConnected.value = false
}

function openStream() {
  closeStream()
  stream = new EventSource(`/api/caddy/runtime/stream?source=${encodeURIComponent(logSource.value)}`)
  stream.onopen = () => {
    streamConnected.value = true
  }
  stream.onerror = () => {
    streamConnected.value = false
  }
  stream.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data || '{}')
      if (payload?.status) {
        status.value = payload.status
      }
      if (Array.isArray(payload?.logs)) {
        logs.value = [...logs.value, ...payload.logs].slice(-220)
      }
    } catch {
      streamConnected.value = false
    }
  }
}

async function refreshAll() {
  error.value = ''
  try {
    await Promise.all([loadStatus(), loadLogs()])
  } catch (err) {
    error.value = err.message || 'Ошибка загрузки runtime статуса'
  }
}

async function install(reinstall) {
  busy.value = true
  error.value = ''
  try {
    await apiPost('/api/caddy/runtime/install', {
      addons: selectedAddons.value,
      reinstall: Boolean(reinstall),
    })
    await refreshAll()
  } catch (err) {
    error.value = err.message || 'Ошибка установки Caddy runtime'
  } finally {
    busy.value = false
  }
}

async function startContainer() {
  busy.value = true
  error.value = ''
  try {
    await apiPost('/api/caddy/runtime/start', {})
    await refreshAll()
  } catch (err) {
    error.value = err.message || 'Ошибка запуска контейнера'
  } finally {
    busy.value = false
  }
}

async function stopContainer() {
  busy.value = true
  error.value = ''
  try {
    await apiPost('/api/caddy/runtime/stop', {})
    await refreshAll()
  } catch (err) {
    error.value = err.message || 'Ошибка остановки контейнера'
  } finally {
    busy.value = false
  }
}

async function rollback() {
  busy.value = true
  error.value = ''
  try {
    await apiPost('/api/caddy/runtime/rollback', {
      build_id: rollbackBuildId.value || undefined,
    })
    await refreshAll()
  } catch (err) {
    error.value = err.message || 'Ошибка rollback'
  } finally {
    busy.value = false
  }
}

async function loadDefaultCaddyfile() {
  busy.value = true
  error.value = ''
  try {
    await apiPost('/api/caddyfile/default', {})
    await refreshAll()
  } catch (err) {
    error.value = err.message || 'Ошибка генерации Caddyfile'
  } finally {
    busy.value = false
  }
}

function setLogSource(source) {
  logSource.value = source
  logs.value = []
  openStream()
  loadLogs().catch((err) => {
    error.value = err.message || 'Ошибка загрузки логов'
  })
}

onMounted(async () => {
  await refreshAll()
  openStream()
  timer = window.setInterval(() => {
    if (!streamConnected.value) {
      refreshAll().catch(() => null)
    }
  }, 2500)
})

onBeforeUnmount(() => {
  closeStream()
  if (timer) {
    window.clearInterval(timer)
    timer = null
  }
})
</script>

<template>
  <div id="particles-js" class="particles-layer"></div>
  <div class="ambient"></div>
  <div
    v-if="introVisible"
    class="intro-overlay"
    :class="{ leaving: introLeaving, 'auth-error': authErrorPulse }"
    @click.self="handleIntroOverlayClick"
  >
    <div ref="introCardRef" class="intro-card" :class="{ leaving: introLeaving, shake: authShake }" :style="introStyle">
      <div class="intro-card-inner" :class="{ flipped: authFlipped }">
        <div class="intro-face intro-front" @click.stop="handleIntroFrontClick">
          <img src="/janus.png" alt="Janus" />
          <div class="intro-title">Janus</div>
          <div class="intro-subtitle">Caddy · Cloudflare · JSON5</div>
          <div class="intro-hint">{{ introHintText }}</div>
        </div>
        <div v-if="authEnabled && !authAuthorized" class="intro-face intro-back" @click.stop>
          <img src="/janus.png" alt="Janus" />
          <input
            v-model="authPassword"
            class="intro-input"
            type="password"
            placeholder="Пароль"
            @keydown.enter.prevent="submitAuth"
          />
          <button class="primary intro-button" type="button" @click="submitAuth" :disabled="authBusy">Войти</button>
          <small v-if="authError" class="error">{{ authError }}</small>
        </div>
      </div>
    </div>
  </div>
  <div class="app-shell" v-cloak :class="{ 'app-hidden': !appReady, 'app-ready': appReady }">
    <aside class="tab-rail">
      <div class="tab-brand">
        <div class="brand-mark" ref="brandMarkRef">
          <img src="/janus.png" alt="Janus" />
          <div class="brand-text">
            <div class="brand-title">Janus</div>
            <div class="brand-subtitle">Caddy · Cloudflare · JSON5</div>
          </div>
        </div>
      </div>
      <nav class="tab-list" role="tablist" aria-label="Главные разделы">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="tab-btn"
          type="button"
          :class="{ active: activeTab === tab.id }"
          role="tab"
          :aria-selected="activeTab === tab.id"
          @click="activeTab = tab.id"
        >
          <span class="tab-title">{{ tab.label }}</span>
          <span class="tab-meta">{{ tab.hint }}</span>
        </button>
      </nav>
      <div class="tab-footer">
        <StatsCards :active="activeCount" :disabled="disabledCount" />
        <div class="panel auth-panel">
          <div class="auth-icons">
            <button
              v-if="!authEnabled"
              class="icon-btn auth-icon"
              type="button"
              aria-label="Включить авторизацию"
              @click="openAuthConfig"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M6 10V8a6 6 0 1 1 12 0v2h1a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h1zm2 0h8V8a4 4 0 0 0-8 0v2zm4 4a2 2 0 0 1 1 3.732V20h-2v-2.268A2 2 0 0 1 12 14z"
                />
              </svg>
            </button>
            <div v-else class="auth-status" aria-label="Авторизация включена">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M6 10V8a6 6 0 1 1 12 0v2h1a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h1zm2 0h8V8a4 4 0 0 0-8 0v2zm4 4a2 2 0 0 1 1 3.732V20h-2v-2.268A2 2 0 0 1 12 14z"
                />
              </svg>
            </div>
            <button
              v-if="authEnabled && authAuthorized"
              class="icon-btn auth-icon"
              type="button"
              aria-label="Выйти"
              @click="logout"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M5 3h8a2 2 0 0 1 2 2v4h-2V5H5v14h8v-4h2v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2zm9.586 6.586 1.414-1.414L21.828 12l-5.828 3.828-1.414-1.414L17.172 13H9v-2h8.172l-2.586-2.414z" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </aside>

    <div class="page">
      <header class="hero">
        <div>
          <h1>{{ activeTabMeta.title }}</h1>
          <p class="subtitle">{{ activeTabMeta.subtitle }}</p>
        </div>
      </header>

      <section v-show="activeTab === 'routes'" class="tab-panel">
        <main class="layout">
          <RoutesSection
            :routes="routes"
            :loading="loadingRoutes"
            @refresh="loadRoutes"
            @toggle="toggleRoute"
            @edit="startEditRoute"
            @delete="confirmDeleteRoute"
          />

          <aside class="panel">
            <h2>{{ editingRoute ? 'Редактировать маршрут' : 'Добавить маршрут' }}</h2>
            <RouteForm
              ref="routeFormRef"
              :error="routeError"
              :editing="Boolean(editingRoute)"
              @submit="submitRoute"
              @cancel="cancelEdit"
            />
          </aside>
        </main>
      </section>

      <section v-show="activeTab === 'tunnels'" class="tab-panel">
        <CloudflareSection
          :model="cf"
          :loading="loadingCf"
          :status-text="cfStatusText"
          :status-class="cfStatusClass"
          :error="cfError"
          @refresh="loadCf"
          @start-docker="startCfDocker"
          @apply="applyCf"
          @toggle="toggleCf"
          @delete="confirmDeleteCf"
          @save="saveCf"
        />
      </section>

      <section v-show="activeTab === 'configs'" class="tab-panel">
        <L4RoutesSection
          :routes="l4Routes"
          :loading="loadingL4"
          :error="l4Error"
          @update:routes="l4Routes = $event"
          @refresh="loadL4"
          @save="saveL4"
          @show-raw="openRawModal"
        />
      </section>

      <section v-show="activeTab === 'caddy'" class="tab-panel">
        <section class="panel plugin-panel">
          <div class="section-header">
            <div>
              <h2>Настройки плагинов</h2>
              <p class="subtitle">Глобальные параметры (prometheus, trace, geoip, cache, tlsredis, s3, security, crowdsec, realip).</p>
            </div>
            <div class="cf-actions">
              <button class="ghost" type="button" @click="openRawModal">Показать raw</button>
              <button class="ghost" type="button" @click="loadPlugins" :disabled="loadingPlugins">Обновить</button>
              <button class="primary" type="button" @click="savePlugins" :disabled="loadingPlugins">Сохранить</button>
            </div>
          </div>
          <PluginSettingsCards :model="pluginsModel" />
          <small>Взаимоисключающие опции: cache.engine = souin | cache_handler; s3storage vs tlsredis по желанию.</small>
          <p class="error">{{ pluginsError }}</p>
        </section>
      </section>

      <section v-show="activeTab === 'converter'" class="tab-panel">
        <CaddyConverterSection
          :caddy-input="caddyInput"
          :convert-result="convertResult"
          :converting="converting"
          :error="rawError"
          @update:caddy-input="caddyInput = $event"
          @convert="convertCaddyfile"
        />
      </section>
    </div>
  </div>

  <ToastBar :visible="toast.visible" :message="toast.message" />
  <ConfirmModal
    :open="confirm.open"
    :title="confirm.title"
    :message="confirm.message"
    :confirm-label="confirm.confirmLabel"
    :cancel-label="confirm.cancelLabel"
    @confirm="handleConfirm"
    @cancel="closeConfirm"
  />
  <RawConfigModal
    :open="rawModalOpen"
    :routes-text="rawModalRoutes"
    :config-text="rawConfig"
    :validated="rawValidated"
    :can-apply="rawCanApply"
    :validating="rawValidationLoading"
    :applying="rawApplyLoading"
    :error="rawValidationError"
    @update:routes-text="rawModalRoutes = $event"
    @validate="validateRawModal"
    @apply="applyRawModal"
    @close="closeRawModal"
  />

  <div v-if="authConfigOpen" class="modal-backdrop" @click.self="closeAuthConfig">
    <div class="modal">
      <h3>Включить авторизацию</h3>
      <p>Задайте пароль для входа. Он будет сохранён в файле <code>auth.txt</code>.</p>
      <div class="field">
        <label>Пароль</label>
        <input v-model="authConfigPassword" type="password" placeholder="Введите пароль" />
      </div>
      <small v-if="authConfigError" class="error">{{ authConfigError }}</small>
      <div class="modal-actions">
        <button class="ghost" type="button" @click="closeAuthConfig" :disabled="authConfigBusy">Отмена</button>
        <button class="primary" type="button" @click="applyAuthConfig" :disabled="authConfigBusy">Включить</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import StatsCards from './components/StatsCards.vue'
import RoutesSection from './components/RoutesSection.vue'
import RouteForm from './components/RouteForm.vue'
import CloudflareSection from './components/CloudflareSection.vue'
import PluginSettingsCards from './components/PluginSettingsCards.vue'
import L4RoutesSection from './components/L4RoutesSection.vue'
import RawConfigModal from './components/RawConfigModal.vue'
import CaddyConverterSection from './components/CaddyConverterSection.vue'
import ToastBar from './components/ToastBar.vue'
import ConfirmModal from './components/ConfirmModal.vue'
import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from './services/api.js'

const tabs = [
  {
    id: 'routes',
    label: 'Маршруты',
    hint: 'Добавление и управление',
    title: 'Маршруты и добавления',
    subtitle: 'Управляйте доменами, wildcard и быстрыми правками без ручной правки config.',
  },
  {
    id: 'tunnels',
    label: 'Тунели',
    hint: 'Cloudflare, hostnames',
    title: 'Тунели и домены',
    subtitle: 'Подключение Cloudflare, управление hostnames и состояние tunnel.',
  },
  {
    id: 'configs',
    label: 'Конфигурации',
    hint: 'L4 / TCP маршруты',
    title: 'Конфигурации',
    subtitle: 'TCP/L4 маршруты для SSH, баз данных и внешних сервисов.',
  },
  {
    id: 'caddy',
    label: 'Настройка Caddy',
    hint: 'Плагины и Raw',
    title: 'Настройка Caddy',
    subtitle: 'Плагины, raw JSON5 и конвертер из Caddyfile.',
  },
  {
    id: 'converter',
    label: 'Конвертер',
    hint: 'Caddyfile → JSON5',
    title: 'Конвертер Caddyfile',
    subtitle: 'Отдельный адаптер Caddyfile в JSON5 с быстрым предпросмотром.',
  },
]
const activeTab = ref('routes')

const introVisible = ref(true)
const introLeaving = ref(false)
const introStyle = ref({})
const introCardRef = ref(null)
const brandMarkRef = ref(null)
const appReady = ref(false)
let introTimer = null

const authEnabled = ref(false)
const authAuthorized = ref(false)
const authFlipped = ref(false)
const authPassword = ref('')
const authError = ref('')
const authBusy = ref(false)
const authShake = ref(false)
const authErrorPulse = ref(false)
const authConfigOpen = ref(false)
const authConfigPassword = ref('')
const authConfigError = ref('')
const authConfigBusy = ref(false)
let idleTimer = null

const routes = ref([])
const loadingRoutes = ref(true)
const routeError = ref('')
const routeFormRef = ref(null)
const editingRoute = ref(null)

const cf = reactive({
  configured: false,
  defaultService: '',
  hostnames: [],
  fallback: '',
})
const loadingCf = ref(true)
const cfError = ref('')

const rawRoutes = ref('')
const rawConfig = ref('')
const loadingRaw = ref(true)
const rawError = ref('')
const caddyInput = ref('')
const convertResult = ref('')
const converting = ref(false)

const pluginsModel = ref(defaultPlugins())
const pluginsError = ref('')
const loadingPlugins = ref(false)

const l4Routes = ref([])
const l4Error = ref('')
const loadingL4 = ref(false)

const rawModalOpen = ref(false)
const rawModalRoutes = ref('')
const rawValidated = ref(false)
const rawLastValidated = ref('')
const rawValidationError = ref('')
const rawValidationLoading = ref(false)
const rawApplyLoading = ref(false)

const toast = reactive({
  visible: false,
  message: '',
})

const confirm = reactive({
  open: false,
  title: '',
  message: '',
  confirmLabel: 'Удалить',
  cancelLabel: 'Отмена',
  onConfirm: null,
})

const activeCount = computed(() => routes.value.filter((route) => route.enabled).length)
const disabledCount = computed(() => routes.value.length - activeCount.value)
const cfStatusText = computed(() => (cf.configured ? 'Подключено' : 'Нет API'))
const cfStatusClass = computed(() => (cf.configured ? 'ok' : 'warn'))
const activeTabMeta = computed(() => tabs.find((tab) => tab.id === activeTab.value) || tabs[0])
const rawCanApply = computed(
  () => rawValidated.value && rawModalRoutes.value === rawLastValidated.value && !rawApplyLoading.value
)

watch(rawModalRoutes, (value) => {
  if (value !== rawLastValidated.value) {
    rawValidated.value = false
  }
})

function showToast(message) {
  toast.message = message
  toast.visible = true
  setTimeout(() => {
    toast.visible = false
  }, 2400)
}

function clearIdleTimer() {
  if (idleTimer) {
    clearTimeout(idleTimer)
    idleTimer = null
  }
}

function scheduleIdleTimer() {
  clearIdleTimer()
  if (!authEnabled.value || !authAuthorized.value) return
  idleTimer = window.setTimeout(() => {
    logout('idle')
  }, 10 * 60 * 1000)
}

function handleUserActivity() {
  if (!authEnabled.value || !authAuthorized.value) return
  scheduleIdleTimer()
}

function defaultPlugins() {
  return {
    tlsredis: {
      address: '',
      db: null,
      username: null,
      password: null,
      key_prefix: null,
    },
    realip: { presets: ['cloudflare'], cidrs: [] },
    prometheus: { enabled: false, path: '/metrics' },
    trace: { enabled: false, exporter: { otlp_endpoint: '', headers: {} } },
    geoip: { enabled: false, action: 'block', countries: [], asn: [] },
    crowdsec: { enabled: false, lapi_url: '', api_key: '', fallback_action: 'allow' },
    security: { portal_name: 'secure', issuers: [], jwt: {} },
    appsec: { enabled: false, policy: 'owasp' },
    cache: { enabled: false, engine: 'souin', ttl: '120s', excluded_paths: [], key_strategy: 'path' },
    docker_proxy: { enabled: false, labels_filter: '' },
    s3storage: { enabled: false, bucket: '', region: '', endpoint: '', access_key: '', secret_key: '' },
    fs_s3: { enabled: false, bucket: '', region: '', endpoint: '', access_key: '', secret_key: '', root: '/', browse: false },
  }
}

function mergeDefaults(base, value) {
  if (Array.isArray(base)) {
    return Array.isArray(value) ? value : base
  }
  if (base && typeof base === 'object') {
    const next = { ...base }
    if (value && typeof value === 'object') {
      for (const [key, val] of Object.entries(value)) {
        next[key] = mergeDefaults(base[key], val)
      }
    }
    return next
  }
  return value !== undefined ? value : base
}

function isHttpUrl(value) {
  return /^https?:\/\//i.test(String(value || '').trim())
}

function isDuration(value) {
  return /^\d+(ms|s|m|h|d)$/i.test(String(value || '').trim())
}

function isCountryCode(value) {
  return /^[A-Z]{2}$/.test(String(value || '').trim())
}

function isAsn(value) {
  return /^(AS)?\d+$/i.test(String(value || '').trim())
}

function isCidr(value) {
  const text = String(value || '').trim()
  if (!text) return false
  if (/^(\d{1,3}\.){3}\d{1,3}\/\d{1,2}$/.test(text)) return true
  if (/^[0-9a-fA-F:]+\/\d{1,3}$/.test(text)) return true
  return false
}

function validatePlugins(model) {
  const errors = []
  if (model.prometheus?.enabled) {
    const path = String(model.prometheus.path || '').trim()
    if (!path) errors.push('Prometheus: требуется path.')
    if (path && !path.startsWith('/')) errors.push('Prometheus: path должен начинаться с /.')
  }
  if (model.trace?.enabled) {
    const endpoint = String(model.trace.exporter?.otlp_endpoint || '').trim()
    if (!endpoint) errors.push('Trace: требуется otlp_endpoint.')
    if (endpoint && !isHttpUrl(endpoint)) errors.push('Trace: otlp_endpoint должен начинаться с http:// или https://.')
  }
  if (model.geoip?.enabled && !['block', 'allow'].includes(model.geoip.action)) {
    errors.push('GeoIP: action должен быть block или allow.')
  }
  if (model.geoip?.enabled) {
    const countries = model.geoip.countries || []
    const asn = model.geoip.asn || []
    if (!countries.length && !asn.length) errors.push('GeoIP: требуется хотя бы одна страна или ASN.')
    const badCountries = countries.filter((c) => !isCountryCode(c))
    if (badCountries.length) errors.push(`GeoIP: страны должны быть в формате ISO2 (например, RU). Ошибка: ${badCountries.join(', ')}`)
    const badAsn = asn.filter((a) => !isAsn(a))
    if (badAsn.length) errors.push(`GeoIP: ASN должен быть в формате AS12345. Ошибка: ${badAsn.join(', ')}`)
  }
  if (model.crowdsec?.enabled) {
    if (!model.crowdsec.lapi_url) errors.push('CrowdSec: требуется lapi_url.')
    if (!model.crowdsec.api_key) errors.push('CrowdSec: требуется api_key.')
    if (model.crowdsec.lapi_url && !isHttpUrl(model.crowdsec.lapi_url)) {
      errors.push('CrowdSec: lapi_url должен начинаться с http:// или https://.')
    }
  }
  if (model.appsec?.enabled && !['owasp', 'strict'].includes(model.appsec.policy)) {
    errors.push('AppSec: policy должен быть owasp или strict.')
  }
  if (model.cache?.enabled) {
    if (!['souin', 'cache_handler'].includes(model.cache.engine)) {
      errors.push('Cache: engine должен быть souin или cache_handler.')
    }
    if (model.cache.ttl && !isDuration(model.cache.ttl)) {
      errors.push('Cache: ttl должен быть в формате 120s, 5m, 1h.')
    }
    const badPaths = (model.cache.excluded_paths || []).filter((p) => p && !String(p).startsWith('/'))
    if (badPaths.length) errors.push(`Cache: excluded_paths должен начинаться с /. Ошибка: ${badPaths.join(', ')}`)
  }
  const badCidrs = (model.realip?.cidrs || []).filter((cidr) => !isCidr(cidr))
  if (badCidrs.length) errors.push(`RealIP: CIDR некорректен. Ошибка: ${badCidrs.join(', ')}`)
  if (model.tlsredis) {
    const hasAny =
      String(model.tlsredis.address || '').trim() ||
      String(model.tlsredis.username || '').trim() ||
      String(model.tlsredis.password || '').trim() ||
      String(model.tlsredis.key_prefix || '').trim() ||
      model.tlsredis.db !== null
    if (hasAny && !String(model.tlsredis.address || '').trim()) {
      errors.push('TLS Redis: требуется address.')
    }
  }
  if (model.s3storage?.enabled) {
    if (!model.s3storage.bucket) errors.push('S3 Storage: требуется bucket.')
    if (!model.s3storage.region) errors.push('S3 Storage: требуется region.')
    if (!model.s3storage.access_key) errors.push('S3 Storage: требуется access_key.')
    if (!model.s3storage.secret_key) errors.push('S3 Storage: требуется secret_key.')
  }
  if (model.fs_s3?.enabled) {
    if (!model.fs_s3.bucket) errors.push('FS S3: требуется bucket.')
    if (!model.fs_s3.region) errors.push('FS S3: требуется region.')
    if (!model.fs_s3.access_key) errors.push('FS S3: требуется access_key.')
    if (!model.fs_s3.secret_key) errors.push('FS S3: требуется secret_key.')
  }
  return errors
}

async function loadRoutes() {
  loadingRoutes.value = true
  try {
    const data = await apiGet('/api/routes')
    routes.value = data.routes || []
  } catch (error) {
    showToast(error.message)
  } finally {
    loadingRoutes.value = false
  }
}

function startEditRoute(route) {
  editingRoute.value = route
  routeFormRef.value?.prefill(route)
}

function cancelEdit() {
  editingRoute.value = null
  routeFormRef.value?.reset()
  routeError.value = ''
}

async function submitRoute(payload, reset) {
  routeError.value = ''
  try {
    const wasEditing = Boolean(editingRoute.value)
    if (editingRoute.value) {
      await apiPut(`/api/routes/${editingRoute.value.id}`, payload)
      editingRoute.value = null
    } else {
      await apiPost('/api/routes', payload)
    }
    reset?.()
    await loadRoutes()
    await loadRaw()
    showToast(wasEditing ? 'Маршрут обновлен' : 'Маршрут добавлен')
  } catch (error) {
    routeError.value = error.message || 'Ошибка сети'
  }
}

async function loadRaw() {
  loadingRaw.value = true
  rawError.value = ''
  try {
    const [routesResp, configResp] = await Promise.all([
      apiGet('/api/raw/routes'),
      apiGet('/api/raw/config'),
    ])
    rawRoutes.value = routesResp?.content || ''
    rawConfig.value = configResp?.content || ''
  } catch (error) {
    rawError.value = error.message || 'Ошибка сети'
  } finally {
    loadingRaw.value = false
  }
}

async function openRawModal() {
  await loadRaw()
  rawModalRoutes.value = rawRoutes.value
  rawValidated.value = false
  rawLastValidated.value = ''
  rawValidationError.value = ''
  rawModalOpen.value = true
}

function closeRawModal() {
  rawModalOpen.value = false
}

async function validateRawModal() {
  rawValidationLoading.value = true
  rawValidationError.value = ''
  try {
    await apiPost('/api/raw/routes/validate', { content: rawModalRoutes.value })
    rawValidated.value = true
    rawLastValidated.value = rawModalRoutes.value
    showToast('Проверка успешна')
  } catch (error) {
    rawValidated.value = false
    rawValidationError.value = error.message || 'Ошибка валидации'
  } finally {
    rawValidationLoading.value = false
  }
}

async function applyRawModal() {
  if (!rawCanApply.value) return
  rawApplyLoading.value = true
  rawValidationError.value = ''
  try {
    await apiPut('/api/raw/routes', { content: rawModalRoutes.value })
    await loadRoutes()
    await loadRaw()
    rawModalOpen.value = false
    showToast('Raw routes сохранены')
  } catch (error) {
    rawValidationError.value = error.message || 'Ошибка сохранения'
  } finally {
    rawApplyLoading.value = false
  }
}

async function loadPlugins() {
  loadingPlugins.value = true
  pluginsError.value = ''
  try {
    const data = await apiGet('/api/plugins')
    pluginsModel.value = mergeDefaults(defaultPlugins(), data || {})
  } catch (error) {
    pluginsError.value = error.message || 'Ошибка загрузки'
  } finally {
    loadingPlugins.value = false
  }
}

async function savePlugins() {
  pluginsError.value = ''
  try {
    const errors = validatePlugins(pluginsModel.value)
    if (errors.length) {
      pluginsError.value = errors.join(' ')
      return
    }
    await apiPut('/api/plugins', pluginsModel.value)
    await loadPlugins()
    await loadRaw()
    showToast('Плагины сохранены')
  } catch (error) {
    pluginsError.value = error.message || 'Ошибка сохранения'
  }
}

async function loadL4() {
  loadingL4.value = true
  l4Error.value = ''
  try {
    const data = await apiGet('/api/l4routes')
    l4Routes.value = data?.l4_routes || []
  } catch (error) {
    l4Error.value = error.message || 'Ошибка загрузки'
  } finally {
    loadingL4.value = false
  }
}

async function saveL4() {
  l4Error.value = ''
  try {
    await apiPut('/api/l4routes', { l4_routes: l4Routes.value })
    await loadL4()
    await loadRaw()
    showToast('L4 сохранены')
  } catch (error) {
    l4Error.value = error.message || 'Ошибка сохранения'
  }
}

async function convertCaddyfile() {
  converting.value = true
  rawError.value = ''
  try {
    const data = await apiPost('/api/convert/caddyfile', { content: caddyInput.value })
    convertResult.value = data?.json5 || ''
  } catch (error) {
    rawError.value = error.message || 'Ошибка конвертации'
  } finally {
    converting.value = false
  }
}

async function toggleRoute(route) {
  try {
    await apiPatch(`/api/routes/${route.id}`, { enabled: !route.enabled })
    await loadRoutes()
    await loadRaw()
    showToast(route.enabled ? 'Маршрут отключен' : 'Маршрут включен')
  } catch (error) {
    showToast(error.message)
  }
}

function confirmDeleteRoute(route) {
  openConfirm({
    title: 'Удалить маршрут?',
    message: `Маршрут ${route.domains.join(', ')} будет удалён.`,
    confirmLabel: 'Удалить',
    onConfirm: () => deleteRoute(route),
  })
}

async function deleteRoute(route) {
  try {
    await apiDelete(`/api/routes/${route.id}`)
    await loadRoutes()
    await loadRaw()
    showToast('Маршрут удален')
  } catch (error) {
    showToast(error.message)
  }
}

async function loadCf() {
  loadingCf.value = true
  try {
    const data = await apiGet('/api/cf/hostnames')
    cf.configured = Boolean(data.configured)
    cf.defaultService = data.default_service || ''
    cf.hostnames = data.hostnames || []
    cf.fallback = data.fallback || 'http_status:404'
  } catch (error) {
    showToast(error.message)
  } finally {
    loadingCf.value = false
  }
}

async function applyCf() {
  try {
    await apiPost('/api/cf/apply')
    showToast('Cloudflare обновлен')
  } catch (error) {
    showToast(error.message)
  }
}

async function startCfDocker() {
  try {
    await apiPost('/api/cf/docker/start', {})
    showToast('Tunnel контейнер запущен')
    await loadCf()
  } catch (error) {
    showToast(error.message)
  }
}

async function saveCf(payload, reset) {
  cfError.value = ''
  try {
    await apiPost('/api/cf/hostnames', payload)
    reset?.()
    await loadCf()
    showToast('Hostname сохранен')
  } catch (error) {
    cfError.value = error.message || 'Ошибка сети'
  }
}

async function toggleCf(entry) {
  try {
    await apiPatch(`/api/cf/hostnames/${encodeURIComponent(entry.hostname)}`, {
      enabled: !entry.enabled,
    })
    await loadCf()
    showToast(entry.enabled ? 'Tunnel отключен' : 'Tunnel включен')
  } catch (error) {
    showToast(error.message)
  }
}

function confirmDeleteCf(entry) {
  openConfirm({
    title: 'Удалить hostname?',
    message: `${entry.hostname} будет удалён из Cloudflare.`,
    confirmLabel: 'Удалить',
    onConfirm: () => deleteCf(entry),
  })
}

async function deleteCf(entry) {
  try {
    await apiDelete(`/api/cf/hostnames/${encodeURIComponent(entry.hostname)}`)
    await loadCf()
    showToast('Hostname удален')
  } catch (error) {
    showToast(error.message)
  }
}

function openConfirm({ title, message, confirmLabel, cancelLabel, onConfirm }) {
  confirm.open = true
  confirm.title = title
  confirm.message = message
  confirm.confirmLabel = confirmLabel || 'Удалить'
  confirm.cancelLabel = cancelLabel || 'Отмена'
  confirm.onConfirm = onConfirm
}

function closeConfirm() {
  confirm.open = false
  confirm.onConfirm = null
}

async function handleConfirm() {
  if (!confirm.onConfirm) return
  const action = confirm.onConfirm
  closeConfirm()
  await action()
}

function dismissIntro() {
  if (!introVisible.value || introLeaving.value) return
  introLeaving.value = true
  if (introTimer) {
    clearTimeout(introTimer)
    introTimer = null
  }
  nextTick(() => {
    const introRect = introCardRef.value?.getBoundingClientRect()
    const targetRect = brandMarkRef.value?.getBoundingClientRect()
    if (introRect && targetRect) {
      const dx = targetRect.left + targetRect.width / 2 - (introRect.left + introRect.width / 2)
      const hiddenOffsetY = 32
      const dy = targetRect.top + targetRect.height / 2 - (introRect.top + introRect.height / 2) - hiddenOffsetY
      const scale = Math.max(0.18, Math.min(0.35, targetRect.height / introRect.height))
      introStyle.value = {
        '--intro-x': `${dx}px`,
        '--intro-y': `${dy}px`,
        '--intro-scale': scale.toFixed(3),
      }
    }
    appReady.value = true
    window.setTimeout(() => {
      introVisible.value = false
      introLeaving.value = false
    }, 650)
  })
}

function scheduleIntroDismiss() {
  if (introTimer) {
    clearTimeout(introTimer)
  }
  introTimer = window.setTimeout(dismissIntro, 3000)
}

function handleIntroOverlayClick() {
  if (authEnabled.value && !authAuthorized.value) return
  dismissIntro()
}

function handleIntroFrontClick() {
  if (authEnabled.value && !authAuthorized.value) {
    authFlipped.value = true
    return
  }
  dismissIntro()
}

function triggerAuthError(message) {
  authError.value = message
  authShake.value = true
  authErrorPulse.value = true
  window.setTimeout(() => {
    authShake.value = false
    authErrorPulse.value = false
  }, 500)
}

async function submitAuth() {
  if (!authPassword.value.trim()) {
    triggerAuthError('Введите пароль')
    return
  }
  authBusy.value = true
  try {
    await apiPost('/api/auth/login', { password: authPassword.value })
    authAuthorized.value = true
    authError.value = ''
    authFlipped.value = false
    authPassword.value = ''
    bootstrapData()
    scheduleIdleTimer()
    window.setTimeout(() => {
      dismissIntro()
    }, 350)
  } catch (error) {
    triggerAuthError('Неверный пароль')
  } finally {
    authBusy.value = false
  }
}

function showAuthGate() {
  introVisible.value = true
  introLeaving.value = false
  appReady.value = false
  authFlipped.value = false
  authPassword.value = ''
  authError.value = ''
  authErrorPulse.value = false
  authShake.value = false
}

async function logout(reason = 'manual') {
  try {
    await apiPost('/api/auth/logout', {})
  } catch (error) {
    // ignore logout errors
  }
  authAuthorized.value = false
  clearIdleTimer()
  if (authEnabled.value) {
    showAuthGate()
  }
  if (reason === 'manual') {
    showToast('Вы вышли')
  }
}

function openAuthConfig() {
  authConfigError.value = ''
  authConfigPassword.value = ''
  authConfigOpen.value = true
}

function closeAuthConfig() {
  if (authConfigBusy.value) return
  authConfigOpen.value = false
}

async function applyAuthConfig() {
  if (!authConfigPassword.value.trim()) {
    authConfigError.value = 'Введите пароль'
    return
  }
  authConfigBusy.value = true
  authConfigError.value = ''
  try {
    await apiPut('/api/auth/config', { enabled: true, password: authConfigPassword.value.trim() })
    authEnabled.value = true
    authAuthorized.value = true
    authConfigOpen.value = false
    scheduleIdleTimer()
    showToast('Авторизация включена')
  } catch (error) {
    authConfigError.value = error.message || 'Ошибка сохранения'
  } finally {
    authConfigBusy.value = false
  }
}

async function initAuth() {
  try {
    const status = await apiGet('/api/auth/status')
    authEnabled.value = Boolean(status.enabled)
    authAuthorized.value = Boolean(status.authorized)
  } catch (error) {
    authEnabled.value = false
    authAuthorized.value = true
  }

  if (authEnabled.value && !authAuthorized.value) {
    showAuthGate()
    return
  }
  scheduleIntroDismiss()
  bootstrapData()
  scheduleIdleTimer()
}

function bootstrapData() {
  loadRoutes()
  loadRaw()
  loadPlugins()
  loadL4()
  loadCf()
}

const introHintText = computed(() => {
  if (authEnabled.value && !authAuthorized.value) {
    return 'Нажмите для входа'
  }
  return 'Нажмите, чтобы продолжить'
})

onMounted(() => {
  if (window.particlesJS) {
    window.particlesJS('particles-js', {
      particles: {
        number: { value: 70, density: { enable: true, value_area: 900 } },
        color: { value: '#a78bfa' },
        shape: { type: 'circle' },
        opacity: { value: 0.35, random: true },
        size: { value: 2.6, random: true },
        line_linked: {
          enable: true,
          distance: 130,
          color: '#7c3aed',
          opacity: 0.2,
          width: 1,
        },
        move: { enable: true, speed: 1.1 },
      },
      interactivity: {
        events: { onhover: { enable: true, mode: 'repulse' } },
        modes: { repulse: { distance: 140 } },
      },
      retina_detect: true,
    })
  }
  initAuth()
  window.addEventListener('click', handleUserActivity, true)
  window.addEventListener('keydown', handleUserActivity, true)
})

onBeforeUnmount(() => {
  if (introTimer) {
    clearTimeout(introTimer)
    introTimer = null
  }
  clearIdleTimer()
  window.removeEventListener('click', handleUserActivity, true)
  window.removeEventListener('keydown', handleUserActivity, true)
})
</script>

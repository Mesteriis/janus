<template>
  <section class="panel">
    <div class="section-header">
      <div>
        <h2>L4 / TCP маршруты</h2>
        <p class="subtitle">Слушатели, SNI/ALPN и upstream'ы для SSH/DB и др.</p>
      </div>
      <div class="cf-actions">
        <button class="ghost" type="button" @click="$emit('show-raw')">Показать raw</button>
        <button class="ghost" type="button" @click="$emit('refresh')" :disabled="loading">Обновить</button>
        <button class="primary" type="button" @click="$emit('save')" :disabled="loading">Сохранить</button>
      </div>
    </div>

    <div v-if="loading" class="empty">Загружаем L4 маршруты...</div>
    <div v-else>
      <div v-if="!routes.length" class="empty">L4 маршрутов пока нет.</div>
      <div v-else class="routes-grid">
        <div v-for="(route, idx) in routes" :key="idx" class="route-card">
          <div class="route-header">
            <div>
              <h4 class="route-title">{{ route.listen || 'listen: ?' }}</h4>
              <p class="route-upstream">
                {{ (route.proxy?.upstreams || []).map((u) => u.dial || '').join(', ') || 'upstreams: —' }}
              </p>
            </div>
            <span class="badge enabled">L4</span>
          </div>
          <div class="route-meta">
            <span v-if="route.match?.sni?.length" class="tag">SNI: {{ route.match.sni.join(', ') }}</span>
            <span v-if="route.match?.alpn?.length" class="tag">ALPN: {{ route.match.alpn.join(', ') }}</span>
          </div>
          <div class="route-actions">
            <button class="ghost" type="button" @click="startEdit(idx)">Редактировать</button>
            <button class="danger" type="button" @click="removeRoute(idx)">Удалить</button>
          </div>
        </div>
      </div>

      <div class="panel">
        <h3>{{ editingIndex === null ? 'Добавить L4 маршрут' : 'Редактировать L4 маршрут' }}</h3>
        <div class="field">
          <label>Listen</label>
          <input v-model="form.listen" type="text" placeholder=":22" />
        </div>
        <div class="field">
          <label>Upstreams</label>
          <TagListInput v-model="form.upstreams" placeholder="10.0.0.1:22" />
        </div>
        <details class="advanced">
          <summary>Advanced</summary>
          <div class="row">
            <div class="field">
              <label>Max connections</label>
              <input v-model="form.maxConnections" type="number" min="0" placeholder="100" />
            </div>
            <div class="field">
              <label>Idle timeout</label>
              <input v-model="form.idleTimeout" type="text" placeholder="30s" />
            </div>
          </div>
          <div class="field">
            <label>SNI</label>
            <TagListInput v-model="form.sni" placeholder="ssh.example.com" />
          </div>
          <div class="field">
            <label>ALPN</label>
            <TagListInput v-model="form.alpn" placeholder="ssh" />
          </div>
        </details>
        <div class="route-actions">
          <button class="ghost" type="button" @click="resetForm">Сбросить</button>
          <button class="primary" type="button" @click="saveRoute">{{ editingIndex === null ? 'Добавить' : 'Обновить' }}</button>
        </div>
        <p class="error">{{ localError || error }}</p>
      </div>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import TagListInput from './TagListInput.vue'

const props = defineProps({
  routes: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['update:routes', 'refresh', 'save', 'show-raw'])

const editingIndex = ref(null)
const localError = ref('')

const form = reactive({
  listen: '',
  upstreams: [],
  sni: [],
  alpn: [],
  maxConnections: '',
  idleTimeout: '',
})

function resetForm() {
  form.listen = ''
  form.upstreams = []
  form.sni = []
  form.alpn = []
  form.maxConnections = ''
  form.idleTimeout = ''
  editingIndex.value = null
  localError.value = ''
}

function startEdit(idx) {
  const route = props.routes[idx]
  if (!route) return
  editingIndex.value = idx
  form.listen = route.listen || ''
  form.upstreams = (route.proxy?.upstreams || []).map((u) => u.dial || '').filter(Boolean)
  form.sni = route.match?.sni ? [...route.match.sni] : []
  form.alpn = route.match?.alpn ? [...route.match.alpn] : []
  form.maxConnections = route.proxy?.max_connections ?? ''
  form.idleTimeout = route.proxy?.idle_timeout ?? ''
}

function removeRoute(idx) {
  const next = [...props.routes]
  next.splice(idx, 1)
  emit('update:routes', next)
  if (editingIndex.value === idx) resetForm()
}

function buildRoute() {
  return {
    listen: form.listen.trim(),
    match: {
      ...(form.sni.length ? { sni: [...form.sni] } : {}),
      ...(form.alpn.length ? { alpn: [...form.alpn] } : {}),
    },
    proxy: {
      upstreams: form.upstreams.map((dial) => ({ dial })),
      ...(form.maxConnections !== '' ? { max_connections: Number(form.maxConnections) } : {}),
      ...(form.idleTimeout ? { idle_timeout: form.idleTimeout } : {}),
    },
  }
}

function extractPort(value) {
  const text = String(value || '').trim()
  if (!text) return null
  if (text.startsWith('[')) {
    const match = /^\[[0-9a-fA-F:]+\\]:(\\d+)$/.exec(text)
    return match ? match[1] : null
  }
  const parts = text.split(':')
  if (parts.length < 2) return null
  const port = parts[parts.length - 1]
  if (!/^\\d+$/.test(port)) return null
  return port
}

function isValidPort(port) {
  const num = Number(port)
  return Number.isInteger(num) && num > 0 && num <= 65535
}

function validateForm() {
  if (!form.listen.trim()) return 'Listen обязателен.'
  if (!form.upstreams.length) return 'Нужен хотя бы один upstream.'
  const listenPort = extractPort(form.listen)
  if (!listenPort || !isValidPort(listenPort)) return 'Listen должен быть в формате host:port или :port.'
  const badUpstreams = form.upstreams.filter((dial) => {
    const port = extractPort(dial)
    return !port || !isValidPort(port)
  })
  if (badUpstreams.length) return `Upstream должен быть в формате host:port. Ошибка: ${badUpstreams.join(', ')}`
  return ''
}

function saveRoute() {
  localError.value = validateForm()
  if (localError.value) return

  const next = [...props.routes]
  const route = buildRoute()
  if (editingIndex.value === null) {
    next.push(route)
  } else {
    next[editingIndex.value] = route
  }
  emit('update:routes', next)
  resetForm()
}
</script>

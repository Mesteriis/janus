<template>
  <div class="card-section">
    <h3>Observability</h3>
    <div class="card-grid">
      <div class="panel card">
        <div class="card-header">
          <h4>Prometheus</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('prometheus')" aria-label="О плагине Prometheus">i</button>
            <label class="toggle">
              <input v-model="model.prometheus.enabled" type="checkbox" />
              Включить
            </label>
          </div>
        </div>
        <div class="field">
          <label>Путь метрик</label>
          <input v-model="model.prometheus.path" type="text" placeholder="/metrics" :disabled="!model.prometheus.enabled" />
        </div>
      </div>

      <div class="panel card">
        <div class="card-header">
          <h4>Trace</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('trace')" aria-label="О плагине Trace">i</button>
            <label class="toggle">
              <input v-model="model.trace.enabled" type="checkbox" />
              Включить
            </label>
          </div>
        </div>
        <div class="field">
          <label>OTLP endpoint</label>
          <input v-model="model.trace.exporter.otlp_endpoint" type="text" placeholder="http://otel:4318" :disabled="!model.trace.enabled" />
        </div>
        <div class="field">
          <label>Headers</label>
          <KeyValueInput v-model="model.trace.exporter.headers" />
        </div>
      </div>
    </div>
  </div>

  <div class="card-section">
    <h3>Security & WAF</h3>
    <div class="card-grid">
      <div class="panel card">
        <div class="card-header">
          <h4>GeoIP</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('geoip')" aria-label="О плагине GeoIP">i</button>
            <label class="toggle">
              <input v-model="model.geoip.enabled" type="checkbox" />
              Включить
            </label>
          </div>
        </div>
        <div class="field">
          <label>Action</label>
          <select v-model="model.geoip.action" :disabled="!model.geoip.enabled">
            <option value="block">block</option>
            <option value="allow">allow</option>
          </select>
        </div>
        <div class="field">
          <label>Countries</label>
          <TagListInput v-model="model.geoip.countries" placeholder="RU, US" />
        </div>
        <div class="field">
          <label>ASN</label>
          <TagListInput v-model="model.geoip.asn" placeholder="AS12345" />
        </div>
      </div>

      <div class="panel card">
        <div class="card-header">
          <h4>CrowdSec</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('crowdsec')" aria-label="О плагине CrowdSec">i</button>
            <label class="toggle">
              <input v-model="model.crowdsec.enabled" type="checkbox" />
              Включить
            </label>
          </div>
        </div>
        <div class="field">
          <label>LAPI URL</label>
          <input v-model="model.crowdsec.lapi_url" type="text" placeholder="http://crowdsec:8080" :disabled="!model.crowdsec.enabled" />
        </div>
        <div class="field">
          <label>API key</label>
          <input v-model="model.crowdsec.api_key" type="password" placeholder="xxxxxxxx" :disabled="!model.crowdsec.enabled" />
        </div>
        <div class="field">
          <label>Fallback</label>
          <select v-model="model.crowdsec.fallback_action" :disabled="!model.crowdsec.enabled">
            <option value="allow">allow</option>
            <option value="deny">deny</option>
          </select>
        </div>
      </div>

      <div class="panel card">
        <div class="card-header">
          <h4>Security Portal</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('security')" aria-label="О плагине Security">i</button>
          </div>
        </div>
        <div class="field">
          <label>Portal name</label>
          <input v-model="model.security.portal_name" type="text" placeholder="secure" />
        </div>
        <div class="field">
          <label>Issuers</label>
          <TagListInput v-model="model.security.issuers" placeholder="issuer-1" />
        </div>
        <div class="field">
          <label>JWT</label>
          <KeyValueInput v-model="model.security.jwt" />
        </div>
      </div>

      <div class="panel card">
        <div class="card-header">
          <h4>AppSec</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('appsec')" aria-label="О плагине AppSec">i</button>
            <label class="toggle">
              <input v-model="model.appsec.enabled" type="checkbox" />
              Включить
            </label>
          </div>
        </div>
        <div class="field">
          <label>Policy</label>
          <select v-model="model.appsec.policy" :disabled="!model.appsec.enabled">
            <option value="owasp">owasp</option>
            <option value="strict">strict</option>
          </select>
        </div>
      </div>
    </div>
  </div>

  <div class="card-section">
    <h3>Cache</h3>
    <div class="card-grid">
      <div class="panel card">
        <div class="card-header">
          <h4>HTTP Cache</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('cache')" aria-label="О плагине Cache">i</button>
            <label class="toggle">
              <input v-model="model.cache.enabled" type="checkbox" />
              Включить
            </label>
          </div>
        </div>
        <div class="field">
          <label>Engine</label>
          <select v-model="model.cache.engine" :disabled="!model.cache.enabled">
            <option value="souin">souin</option>
            <option value="cache_handler">cache_handler</option>
          </select>
        </div>
        <div class="row">
          <div class="field">
            <label>TTL</label>
            <input v-model="model.cache.ttl" type="text" placeholder="120s" :disabled="!model.cache.enabled" />
          </div>
          <div class="field">
            <label>Key strategy</label>
            <select v-model="model.cache.key_strategy" :disabled="!model.cache.enabled">
              <option value="path">path</option>
              <option value="uri">uri</option>
              <option value="host">host</option>
            </select>
          </div>
        </div>
        <div class="field">
          <label>Excluded paths</label>
          <TagListInput v-model="model.cache.excluded_paths" placeholder="/api" />
        </div>
      </div>
    </div>
  </div>

  <div class="card-section">
    <h3>Network</h3>
    <div class="card-grid">
      <div class="panel card">
        <div class="card-header">
          <h4>Real IP</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('realip')" aria-label="О плагине Real IP">i</button>
          </div>
        </div>
        <div class="field">
          <label>Presets</label>
          <div class="row">
            <label class="toggle">
              <input type="checkbox" :checked="hasPreset('cloudflare')" @change="togglePreset('cloudflare')" />
              cloudflare
            </label>
            <label class="toggle">
              <input type="checkbox" :checked="hasPreset('google')" @change="togglePreset('google')" />
              google
            </label>
          </div>
        </div>
        <div class="field">
          <label>CIDRs</label>
          <TagListInput v-model="model.realip.cidrs" placeholder="1.2.3.0/24" />
        </div>
      </div>

      <div class="panel card">
        <div class="card-header">
          <h4>Docker Proxy</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('docker_proxy')" aria-label="О плагине Docker Proxy">i</button>
            <label class="toggle">
              <input v-model="model.docker_proxy.enabled" type="checkbox" />
              Включить
            </label>
          </div>
        </div>
        <div class="field">
          <label>Labels filter</label>
          <input v-model="model.docker_proxy.labels_filter" type="text" placeholder="caddy=enabled" :disabled="!model.docker_proxy.enabled" />
        </div>
      </div>
    </div>
  </div>

  <div class="card-section">
    <h3>Storage</h3>
    <div class="card-grid">
      <div class="panel card">
        <div class="card-header">
          <h4>TLS Redis</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('tlsredis')" aria-label="О плагине TLS Redis">i</button>
          </div>
        </div>
        <div class="field">
          <label>Address</label>
          <input v-model="model.tlsredis.address" type="text" placeholder="127.0.0.1:6379" />
        </div>
        <div class="row">
          <div class="field">
            <label>DB</label>
            <input v-model.number="model.tlsredis.db" type="number" min="0" placeholder="0" />
          </div>
          <div class="field">
            <label>Key prefix</label>
            <input v-model="model.tlsredis.key_prefix" type="text" placeholder="caddy" />
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Username</label>
            <input v-model="model.tlsredis.username" type="text" />
          </div>
          <div class="field">
            <label>Password</label>
            <input v-model="model.tlsredis.password" type="password" />
          </div>
        </div>
      </div>

      <div class="panel card">
        <div class="card-header">
          <h4>S3 Storage</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('s3storage')" aria-label="О плагине S3 Storage">i</button>
            <label class="toggle">
              <input v-model="model.s3storage.enabled" type="checkbox" />
              Включить
            </label>
          </div>
        </div>
        <div class="field">
          <label>Bucket</label>
          <input v-model="model.s3storage.bucket" type="text" :disabled="!model.s3storage.enabled" />
        </div>
        <div class="row">
          <div class="field">
            <label>Region</label>
            <input v-model="model.s3storage.region" type="text" :disabled="!model.s3storage.enabled" />
          </div>
          <div class="field">
            <label>Endpoint</label>
            <input v-model="model.s3storage.endpoint" type="text" :disabled="!model.s3storage.enabled" />
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Access key</label>
            <input v-model="model.s3storage.access_key" type="text" :disabled="!model.s3storage.enabled" />
          </div>
          <div class="field">
            <label>Secret key</label>
            <input v-model="model.s3storage.secret_key" type="password" :disabled="!model.s3storage.enabled" />
          </div>
        </div>
      </div>

      <div class="panel card">
        <div class="card-header">
          <h4>FS S3</h4>
          <div class="card-actions">
            <button class="icon-btn" type="button" @click="openInfo('fs_s3')" aria-label="О плагине FS S3">i</button>
            <label class="toggle">
              <input v-model="model.fs_s3.enabled" type="checkbox" />
              Включить
            </label>
          </div>
        </div>
        <div class="field">
          <label>Bucket</label>
          <input v-model="model.fs_s3.bucket" type="text" :disabled="!model.fs_s3.enabled" />
        </div>
        <div class="row">
          <div class="field">
            <label>Region</label>
            <input v-model="model.fs_s3.region" type="text" :disabled="!model.fs_s3.enabled" />
          </div>
          <div class="field">
            <label>Endpoint</label>
            <input v-model="model.fs_s3.endpoint" type="text" :disabled="!model.fs_s3.enabled" />
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Access key</label>
            <input v-model="model.fs_s3.access_key" type="text" :disabled="!model.fs_s3.enabled" />
          </div>
          <div class="field">
            <label>Secret key</label>
            <input v-model="model.fs_s3.secret_key" type="password" :disabled="!model.fs_s3.enabled" />
          </div>
        </div>
        <div class="row">
          <div class="field">
            <label>Root</label>
            <input v-model="model.fs_s3.root" type="text" :disabled="!model.fs_s3.enabled" />
          </div>
          <label class="toggle">
            <input v-model="model.fs_s3.browse" type="checkbox" :disabled="!model.fs_s3.enabled" />
            Browse
          </label>
        </div>
      </div>
    </div>
  </div>

  <div v-if="infoOpen && currentInfo" class="modal-backdrop" @click.self="closeInfo">
    <div class="modal">
      <h3>{{ currentInfo.title }}</h3>
      <p>{{ currentInfo.description }}</p>
      <div class="links">
        <a v-for="link in currentInfo.links" :key="link.url" :href="link.url" target="_blank" rel="noreferrer">
          {{ link.label }}
        </a>
      </div>
      <div class="modal-actions">
        <button class="ghost" type="button" @click="closeInfo">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import TagListInput from './TagListInput.vue'
import KeyValueInput from './KeyValueInput.vue'
import { computed, ref } from 'vue'

const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
})

const model = props.model

const infoOpen = ref(false)
const infoKey = ref('')

const infoMap = {
  prometheus: {
    title: 'Prometheus',
    description: 'Экспортирует метрики Caddy по HTTP для Prometheus и алертинга.',
    links: [{ label: 'GitHub', url: 'https://github.com/vinissimus/caddy-prometheus' }],
  },
  trace: {
    title: 'Trace',
    description: 'Отправляет трассировки запросов в OTLP (Jaeger/Tempo/OTel).',
    links: [{ label: 'GitHub', url: 'https://github.com/greenpau/caddy-trace' }],
  },
  geoip: {
    title: 'GeoIP',
    description: 'Разрешает или блокирует трафик по странам и ASN.',
    links: [{ label: 'GitHub', url: 'https://github.com/zhangjiayin/caddy-geoip2' }],
  },
  crowdsec: {
    title: 'CrowdSec',
    description: 'Блокирует вредные IP через CrowdSec LAPI.',
    links: [{ label: 'GitHub', url: 'https://github.com/hslatman/caddy-crowdsec-bouncer' }],
  },
  security: {
    title: 'Security Portal',
    description: 'SSO‑портал и JWT защита для приложений.',
    links: [{ label: 'GitHub', url: 'https://github.com/greenpau/caddy-security' }],
  },
  appsec: {
    title: 'AppSec',
    description: 'WAF политики (OWASP/strict) перед прокси. Часть security‑suite.',
    links: [{ label: 'GitHub', url: 'https://github.com/greenpau/caddy-security' }],
  },
  cache: {
    title: 'HTTP Cache',
    description: 'Кэширует ответы (GET/статика) для ускорения.',
    links: [
      { label: 'Souin', url: 'https://github.com/darkweak/souin/tree/master/plugins/caddy' },
      { label: 'Cache Handler', url: 'https://github.com/caddyserver/cache-handler' },
    ],
  },
  realip: {
    title: 'Real IP',
    description: 'Определяет реальный IP клиента за прокси/Cloudflare.',
    links: [{ label: 'GitHub', url: 'https://github.com/captncraig/caddy-realip' }],
  },
  docker_proxy: {
    title: 'Docker Proxy',
    description: 'Автодискавери маршрутов из docker labels.',
    links: [{ label: 'GitHub', url: 'https://github.com/lucaslorentz/caddy-docker-proxy' }],
  },
  tlsredis: {
    title: 'TLS Redis',
    description: 'Хранилище TLS‑сертификатов и OCSP в Redis для нескольких нод.',
    links: [{ label: 'GitHub', url: 'https://github.com/gamalan/caddy-tlsredis' }],
  },
  s3storage: {
    title: 'S3 Storage',
    description: 'Хранилище TLS данных в S3 (серты/OCSP).',
    links: [{ label: 'GitHub', url: 'https://github.com/gsmlg-dev/caddy-storage-s3' }],
  },
  fs_s3: {
    title: 'FS S3',
    description: 'Файловая система поверх S3 для file_server.',
    links: [{ label: 'GitHub', url: 'https://github.com/sagikazarmark/caddy-fs-s3' }],
  },
}

const currentInfo = computed(() => infoMap[infoKey.value] || null)

function openInfo(key) {
  infoKey.value = key
  infoOpen.value = true
}

function closeInfo() {
  infoOpen.value = false
  infoKey.value = ''
}

function hasPreset(name) {
  return (model.realip.presets || []).includes(name)
}

function togglePreset(name) {
  const presets = new Set(model.realip.presets || [])
  if (presets.has(name)) {
    presets.delete(name)
  } else {
    presets.add(name)
  }
  model.realip.presets = Array.from(presets)
}
</script>

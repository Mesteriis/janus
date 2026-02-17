<template>
  <form @submit.prevent="submit" class="route-form" novalidate>
    <div class="field">
      <label for="domains">Домены</label>
      <input id="domains" v-model="form.domains" type="text" placeholder="app.sh-inc.ru, *.example.com" required />
      <small>Через запятую. Wildcard (*.) можно включить переключателем ниже.</small>
    </div>

    <div class="field inline">
      <label class="toggle">
        <input type="checkbox" v-model="form.wildcard" />
        <span>Авто-wildcard</span>
      </label>
      <label class="toggle">
        <input type="checkbox" v-model="form.enabled" />
        <span>Включен</span>
      </label>
    </div>
    <small>Авто‑wildcard добавляет `*.` к каждому домену. Выключенный маршрут не применяется.</small>

    <details class="advanced" :open="openSection === 'overrides'" @toggle="onToggle('overrides', $event)">
      <summary class="accordion-summary">
        <span>Переопределения путей</span>
        <button class="icon-btn small" type="button" @click.stop="openInfo('overrides')" aria-label="Что такое переопределения путей">i</button>
      </summary>
      <div class="field">
        <small>Дополнительные правила для отдельных путей внутри домена.</small>
      </div>
      <div v-if="!form.overrides.length" class="empty">Пути не добавлены.</div>
      <div v-for="(override, index) in form.overrides" :key="override.id || index" class="override-item">
        <div class="field inline">
          <label class="toggle">
            <input type="checkbox" v-model="override.stripPrefix" />
            <span>Убрать префикс</span>
          </label>
          <label class="toggle">
            <input type="checkbox" v-model="override.enabled" />
            <span>Включен</span>
          </label>
        </div>
        <div class="field">
          <label>Путь</label>
          <input v-model="override.path" type="text" placeholder="/api" />
          <small>Укажите путь, к которому применить правило.</small>
        </div>
        <div class="field">
          <label>Методы запроса</label>
          <input v-model="override.methods" type="text" placeholder="GET, POST" />
          <small>Пусто — любые методы.</small>
        </div>
        <div class="field">
          <label>Заголовки (совпадение)</label>
          <textarea v-model="override.matchHeaders" rows="2" placeholder="X-Env: prod"></textarea>
          <small>Запрос должен содержать все указанные заголовки.</small>
        </div>
        <div class="overrides-list">
          <div v-for="(up, uidx) in override.upstreams" :key="uidx" class="override-item slim">
            <div class="row">
              <select v-model="up.scheme">
                <option value="http">http</option>
                <option value="https">https</option>
              </select>
              <input v-model="up.host" type="text" placeholder="192.168.1.51" />
              <input v-model="up.port" type="number" min="1" max="65535" placeholder="8080" />
              <input v-model="up.weight" type="number" min="1" max="100" placeholder="1" />
            </div>
            <small>Протокол, адрес, порт и вес апстрима.</small>
            <div class="override-actions">
              <span class="muted">Апстрим</span>
              <button type="button" class="ghost" @click="removeOverrideUpstream(index, uidx)" :disabled="override.upstreams.length === 1">
                Удалить
              </button>
            </div>
          </div>
          <button class="ghost" type="button" @click="addOverrideUpstream(index)">Добавить апстрим</button>
        </div>
        <div class="field">
          <label>Режим обработки</label>
          <div class="field inline">
            <label class="toggle">
              <input type="radio" value="proxy" v-model="override.mode" />
              <span>Прокси</span>
            </label>
            <label class="toggle">
              <input type="radio" value="redirect" v-model="override.mode" />
              <span>Редирект</span>
            </label>
            <label class="toggle">
              <input type="radio" value="respond" v-model="override.mode" />
              <span>Ответ</span>
            </label>
          </div>
          <small>Что делать с запросом на этом пути.</small>
        </div>
        <div v-if="override.mode === 'redirect'" class="row">
          <input v-model="override.redirectLocation" type="text" placeholder="Адрес перенаправления" />
          <input v-model="override.redirectCode" type="number" min="100" max="599" placeholder="302" />
        </div>
        <div v-if="override.mode === 'respond'">
          <div class="row">
            <input v-model="override.respondStatus" type="number" min="100" max="599" placeholder="200" />
            <input v-model="override.respondContentType" type="text" placeholder="Тип контента (text/plain)" />
          </div>
          <textarea v-model="override.respondBody" rows="2" placeholder="Тело ответа"></textarea>
        </div>
        <small v-if="override.mode === 'redirect'">Адрес и HTTP‑код перенаправления.</small>
        <small v-else-if="override.mode === 'respond'">Статический ответ без обращения к апстриму.</small>
        <button class="ghost" type="button" @click="removeOverride(index)">Удалить путь</button>
      </div>
      <div class="overrides-list">
        <button class="ghost" type="button" @click="addOverride">Добавить путь</button>
      </div>
    </details>

    <details class="advanced" :open="openSection === 'behavior'" @toggle="onToggle('behavior', $event)">
      <summary class="accordion-summary">
        <span>Поведение</span>
        <button class="icon-btn small" type="button" @click.stop="openInfo('behavior')" aria-label="Что такое поведение">i</button>
      </summary>
      <div class="field">
        <label>Режим маршрута</label>
        <div class="field inline">
          <label class="toggle">
            <input type="radio" value="proxy" v-model="form.mode" />
            <span>Прокси</span>
          </label>
          <label class="toggle">
            <input type="radio" value="redirect" v-model="form.mode" />
            <span>Редирект</span>
          </label>
          <label class="toggle">
            <input type="radio" value="respond" v-model="form.mode" />
            <span>Ответ</span>
          </label>
        </div>
        <small>Выберите, как обрабатывать запросы для всего маршрута.</small>
      </div>
      <div v-if="form.mode === 'redirect'" class="row">
        <input v-model="form.redirectLocation" type="text" placeholder="Адрес перенаправления" />
        <input v-model="form.redirectCode" type="number" min="100" max="599" placeholder="302" />
      </div>
      <div v-if="form.mode === 'respond'">
        <div class="row">
          <input v-model="form.respondStatus" type="number" min="100" max="599" placeholder="200" />
          <input v-model="form.respondContentType" type="text" placeholder="Тип контента (text/plain)" />
        </div>
        <textarea v-model="form.respondBody" rows="2" placeholder="Тело ответа"></textarea>
      </div>
      <small v-if="form.mode === 'redirect'">Адрес и HTTP‑код перенаправления.</small>
      <small v-else-if="form.mode === 'respond'">Статический ответ без обращения к апстриму.</small>
    </details>

    <details class="advanced" :open="openSection === 'upstreams'" @toggle="onToggle('upstreams', $event)">
      <summary class="accordion-summary">
        <span>Апстримы и балансировка</span>
        <button class="icon-btn small" type="button" @click.stop="openInfo('upstreams')" aria-label="Что такое апстримы">i</button>
      </summary>
      <div class="overrides-list">
        <div v-for="(up, idx) in form.upstreams" :key="idx" class="override-item">
          <div class="row">
            <select v-model="up.scheme">
              <option value="http">http</option>
              <option value="https">https</option>
            </select>
            <input v-model="up.host" type="text" placeholder="192.168.1.50" required />
            <input v-model="up.port" type="number" min="1" max="65535" placeholder="8080" required />
            <input v-model="up.weight" type="number" min="1" max="100" placeholder="1" />
          </div>
          <small>Протокол, адрес, порт и вес апстрима.</small>
          <div class="override-actions">
            <span class="muted">Апстрим №{{ idx + 1 }}</span>
            <button type="button" class="ghost" @click="removeUpstream(idx)" :disabled="form.upstreams.length === 1">
              Удалить
            </button>
          </div>
        </div>
      </div>
      <div class="overrides-list">
        <button class="ghost" type="button" @click="addUpstream">Добавить апстрим</button>
      </div>
      <div class="field">
        <label for="lb-policy">Балансировка</label>
        <select id="lb-policy" v-model="form.lbPolicy">
          <option value="round_robin">По кругу (round_robin)</option>
          <option value="least_conn">Меньше соединений (least_conn)</option>
          <option value="random">Случайно (random)</option>
          <option value="ip_hash">По IP (ip_hash)</option>
        </select>
        <small>Как распределять нагрузку между апстримами.</small>
      </div>
    </details>

    <details class="advanced" :open="openSection === 'matchers'" @toggle="onToggle('matchers', $event)">
      <summary class="accordion-summary">
        <span>Условия маршрута</span>
        <button class="icon-btn small" type="button" @click.stop="openInfo('matchers')" aria-label="Что такое условия маршрута">i</button>
      </summary>
      <div class="field">
        <label for="methods">Методы запроса</label>
        <input id="methods" v-model="form.methods" type="text" placeholder="GET, POST" />
        <small>Пусто — любые методы. Список через запятую.</small>
      </div>
      <div class="field">
        <label for="match-headers">Заголовки (совпадение)</label>
        <textarea
          id="match-headers"
          v-model="form.matchHeaders"
          rows="2"
          placeholder="X-Env: prod&#10;X-Role: admin"
        ></textarea>
        <small>Каждая строка: `Заголовок: значение1 значение2`</small>
      </div>
    </details>

    <details class="advanced" :open="openSection === 'proxy'" @toggle="onToggle('proxy', $event)">
      <summary class="accordion-summary">
        <span>Опции прокси</span>
        <button class="icon-btn small" type="button" @click.stop="openInfo('proxy')" aria-label="Что такое опции прокси">i</button>
      </summary>
      <div class="field">
        <label for="max-body">Макс. тело (MB)</label>
        <input id="max-body" v-model="form.maxBody" type="number" min="0" placeholder="100" />
        <small>Ограничение размера запроса.</small>
      </div>
      <div class="field">
        <label>Таймауты (сек.)</label>
        <div class="row">
          <input v-model="form.timeoutConnect" type="number" min="0" placeholder="соединение" />
          <input v-model="form.timeoutRead" type="number" min="0" placeholder="чтение" />
          <input v-model="form.timeoutWrite" type="number" min="0" placeholder="запись" />
        </div>
        <small>Если апстрим медленный — увеличьте значения.</small>
      </div>
      <div class="field">
        <label for="headers-up">Заголовки к апстриму</label>
        <textarea id="headers-up" v-model="form.headersUp" rows="2" placeholder="X-Forwarded-Proto: https"></textarea>
        <small>Добавляются к запросу, который идёт на апстрим.</small>
      </div>
      <div class="field">
        <label for="headers-down">Заголовки ответа</label>
        <textarea id="headers-down" v-model="form.headersDown" rows="2" placeholder="Access-Control-Allow-Origin: *"></textarea>
        <small>Добавляются в ответ клиенту.</small>
      </div>
      <div class="field inline">
        <label class="toggle">
          <input type="checkbox" v-model="form.optionsEnabled" />
          <span>Авто-OPTIONS</span>
        </label>
        <input v-if="form.optionsEnabled" v-model="form.optionsStatus" type="number" min="100" max="599" class="small" />
      </div>
      <small>Отвечать на OPTIONS без обращения к апстриму.</small>
      <div class="field">
        <label for="flush-interval">Интервал сброса (flush_interval)</label>
        <input id="flush-interval" v-model="form.proxyFlush" type="text" placeholder="1s" />
        <small>Полезно для стриминга и длительных ответов.</small>
      </div>
      <div class="field inline">
        <label class="toggle">
          <input type="checkbox" v-model="form.proxyBufferReq" />
          <span>Буфер запросов (buffer_requests)</span>
        </label>
        <label class="toggle">
          <input type="checkbox" v-model="form.proxyBufferResp" />
          <span>Буфер ответов (buffer_responses)</span>
        </label>
      </div>
      <small>Включает буферизацию запросов и/или ответов.</small>
    </details>

    <details class="advanced" :open="openSection === 'health'" @toggle="onToggle('health', $event)">
      <summary class="accordion-summary">
        <span>Проверки здоровья</span>
        <button class="icon-btn small" type="button" @click.stop="openInfo('health')" aria-label="Что такое проверки здоровья">i</button>
      </summary>
      <div class="field">
        <label for="ha-path">Путь активной проверки</label>
        <input id="ha-path" v-model="form.healthActivePath" type="text" placeholder="/health" />
        <small>URL, который Caddy будет опрашивать.</small>
      </div>
      <div class="row">
        <input v-model="form.healthActiveInterval" type="text" placeholder="интервал 10s" />
        <input v-model="form.healthActiveTimeout" type="text" placeholder="таймаут 2s" />
      </div>
      <small>Как часто проверять и сколько ждать ответа.</small>
      <div class="field">
        <label for="ha-headers">Заголовки активной проверки</label>
        <textarea id="ha-headers" v-model="form.healthActiveHeaders" rows="2" placeholder="Host: app.sh-inc.ru"></textarea>
        <small>Если сервис требует специальные заголовки.</small>
      </div>
      <div class="field">
        <label for="hp-statuses">Пассивные коды ошибок</label>
        <input id="hp-statuses" v-model="form.healthPassiveStatuses" type="text" placeholder="500,502,503,504" />
        <small>Если ответ с этим кодом — апстрим считается проблемным.</small>
      </div>
      <div class="row">
        <input v-model="form.healthPassiveMaxFails" type="number" min="1" placeholder="макс. ошибок" />
        <input v-model="form.healthPassiveFailDuration" type="text" placeholder="период отключения 30s" />
      </div>
      <small>Сколько ошибок и на какой срок исключать апстрим.</small>
    </details>

    <details class="advanced" :open="openSection === 'transport'" @toggle="onToggle('transport', $event)">
      <summary class="accordion-summary">
        <span>Транспорт</span>
        <button class="icon-btn small" type="button" @click.stop="openInfo('transport')" aria-label="Что такое транспорт">i</button>
      </summary>
      <div class="row">
        <input v-model="form.transportDial" type="text" placeholder="таймаут подключения 5s" />
        <input v-model="form.transportKeepalive" type="text" placeholder="поддержание 60s" />
      </div>
      <small>Таймаут установления соединения (dial_timeout) и keepalive.</small>
      <div class="row">
        <input v-model="form.transportReadBuffer" type="number" min="0" placeholder="буфер чтения" />
        <input v-model="form.transportWriteBuffer" type="number" min="0" placeholder="буфер записи" />
      </div>
      <small>Размеры буферов чтения и записи (read_buffer / write_buffer).</small>
      <label class="toggle">
        <input type="checkbox" v-model="form.transportTlsInsecure" />
        <span>Не проверять TLS (tls_insecure_skip_verify)</span>
      </label>
      <small>Используйте только для тестовых окружений.</small>
    </details>
    <div class="route-actions">
      <button class="primary" type="submit">
        {{ editing ? 'Сохранить маршрут' : 'Создать маршрут' }}
      </button>
      <button v-if="editing" class="ghost" type="button" @click="cancel">Отменить</button>
    </div>
    <p class="error">{{ displayError }}</p>
  </form>

  <div v-if="infoOpen && currentInfo" class="modal-backdrop" @click.self="closeInfo">
    <div class="modal">
      <h3>{{ currentInfo.title }}</h3>
      <p>{{ currentInfo.description }}</p>
      <div class="modal-actions">
        <button class="ghost" type="button" @click="closeInfo">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'

const props = defineProps({
  error: {
    type: String,
    default: '',
  },
  editing: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['submit', 'cancel'])

const localError = ref('')

const emptyUpstream = () => ({
  scheme: 'http',
  host: '',
  port: 80,
  weight: 1,
})

const emptyOverride = () => ({
  id: '',
  path: '',
  stripPrefix: false,
  enabled: true,
  methods: '',
  matchHeaders: '',
  upstreams: [emptyUpstream()],
  mode: 'proxy',
  redirectLocation: '',
  redirectCode: '302',
  respondStatus: '200',
  respondBody: '',
  respondContentType: '',
})

const form = reactive({
  domains: '',
  wildcard: false,
  enabled: true,
  methods: '',
  matchHeaders: '',
  upstreams: [emptyUpstream()],
  lbPolicy: 'round_robin',
  maxBody: 100,
  timeoutConnect: 5,
  timeoutRead: 30,
  timeoutWrite: 30,
  headersUp: '',
  headersDown: '',
  optionsEnabled: false,
  optionsStatus: 204,
  proxyFlush: '1s',
  proxyBufferReq: false,
  proxyBufferResp: false,
  healthActivePath: '/health',
  healthActiveInterval: '10s',
  healthActiveTimeout: '2s',
  healthActiveHeaders: '',
  healthPassiveStatuses: '500,502,503,504',
  healthPassiveMaxFails: 3,
  healthPassiveFailDuration: '30s',
  transportDial: '5s',
  transportKeepalive: '60s',
  transportReadBuffer: 4096,
  transportWriteBuffer: 4096,
  transportTlsInsecure: false,
  mode: 'proxy',
  redirectLocation: '',
  redirectCode: '302',
  respondStatus: '200',
  respondBody: '',
  respondContentType: '',
  overrides: [],
})

const displayError = computed(() => props.error || localError.value)
const openSection = ref('overrides')
const infoOpen = ref(false)
const infoKey = ref('')

const infoMap = {
  matchers: {
    title: 'Условия маршрута',
    description: 'Ограничивает, какие запросы попадут в этот маршрут: методы и заголовки.',
  },
  upstreams: {
    title: 'Апстримы и балансировка',
    description: 'Куда направлять трафик и как распределять нагрузку между адресами.',
  },
  proxy: {
    title: 'Опции прокси',
    description: 'Лимиты тела, таймауты, заголовки и буферизация запросов/ответов.',
  },
  health: {
    title: 'Проверки здоровья',
    description: 'Проверка доступности апстримов и исключение проблемных узлов.',
  },
  transport: {
    title: 'Транспорт',
    description: 'Низкоуровневые параметры соединения до апстрима.',
  },
  behavior: {
    title: 'Поведение',
    description: 'Выберите действие: прокси, редирект или статический ответ.',
  },
  overrides: {
    title: 'Переопределения путей',
    description: 'Дополнительные правила для отдельных путей внутри домена.',
  },
}

const currentInfo = computed(() => infoMap[infoKey.value] || null)

function onToggle(key, event) {
  if (event.target.open) {
    openSection.value = key
  } else if (openSection.value === key) {
    openSection.value = ''
  }
}

function openInfo(key) {
  infoKey.value = key
  infoOpen.value = true
}

function closeInfo() {
  infoOpen.value = false
  infoKey.value = ''
}

function parseHeaderLines(raw) {
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function parseHeaderValues(raw) {
  const lines = parseHeaderLines(raw)
  const dict = {}
  lines.forEach((line) => {
    const [name, ...rest] = line.split(':')
    if (!rest.length) return
    const value = rest.join(':').trim()
    if (!value) return
    dict[name.trim()] = value.split(/[,\\s]+/).filter(Boolean)
  })
  return dict
}

function addUpstream() {
  form.upstreams.push(emptyUpstream())
}

function removeUpstream(index) {
  if (form.upstreams.length === 1) return
  form.upstreams.splice(index, 1)
}

function addOverride() {
  form.overrides.push(emptyOverride())
}

function removeOverride(index) {
  form.overrides.splice(index, 1)
}

function addOverrideUpstream(overrideIndex) {
  form.overrides[overrideIndex].upstreams.push(emptyUpstream())
}

function removeOverrideUpstream(overrideIndex, upstreamIndex) {
  const target = form.overrides[overrideIndex]
  if (target.upstreams.length === 1) return
  target.upstreams.splice(upstreamIndex, 1)
}

function reset() {
  Object.assign(form, {
    domains: '',
    wildcard: false,
    enabled: true,
    methods: '',
    matchHeaders: '',
    upstreams: [emptyUpstream()],
    lbPolicy: 'round_robin',
    maxBody: 100,
    timeoutConnect: 5,
    timeoutRead: 30,
    timeoutWrite: 30,
    headersUp: '',
    headersDown: '',
    optionsEnabled: false,
    optionsStatus: 204,
    proxyFlush: '1s',
    proxyBufferReq: false,
    proxyBufferResp: false,
    healthActivePath: '/health',
    healthActiveInterval: '10s',
    healthActiveTimeout: '2s',
    healthActiveHeaders: '',
    healthPassiveStatuses: '500,502,503,504',
    healthPassiveMaxFails: 3,
    healthPassiveFailDuration: '30s',
    transportDial: '5s',
    transportKeepalive: '60s',
    transportReadBuffer: 4096,
    transportWriteBuffer: 4096,
    transportTlsInsecure: false,
    mode: 'proxy',
    redirectLocation: '',
    redirectCode: '302',
    respondStatus: '200',
    respondBody: '',
    respondContentType: '',
    overrides: [],
  })
  localError.value = ''
}

function headersToLines(headers = {}) {
  return Object.entries(headers)
    .map(([name, value]) => `${name}: ${value}`)
    .join('\n')
}

function headerValuesToLines(headers = {}) {
  return Object.entries(headers)
    .map(([name, values]) => `${name}: ${(values || []).join(' ')}`)
    .join('\n')
}

function prefill(route) {
  reset()
  const domains = Array.isArray(route.domains) ? route.domains : []
  form.domains = domains.join(', ')
  form.enabled = route.enabled !== false
  form.methods = (route.methods || []).join(', ')
  form.matchHeaders = headerValuesToLines(route.match_headers || route.matchHeaders || {})
  form.upstreams =
    (route.upstreams || []).map((u) => ({
      scheme: u.scheme || 'http',
      host: u.host || '',
      port: u.port ?? '',
      weight: u.weight ?? 1,
    })) || [emptyUpstream()]
  if (!form.upstreams.length) form.upstreams = [emptyUpstream()]
  form.lbPolicy = route.lb_policy || 'round_robin'
  form.maxBody =
    route.request_body_max_mb === null || route.request_body_max_mb === undefined
      ? ''
      : route.request_body_max_mb
  form.timeoutConnect = route.timeouts?.connect ?? ''
  form.timeoutRead = route.timeouts?.read ?? ''
  form.timeoutWrite = route.timeouts?.write ?? ''
  form.headersUp = headersToLines(route.headers_up)
  form.headersDown = headersToLines(route.response_headers)
  form.optionsEnabled = Boolean(route.options_response?.enabled)
  form.optionsStatus = route.options_response?.status ?? 204
  form.proxyFlush = route.proxy_opts?.flush_interval || ''
  form.proxyBufferReq = Boolean(route.proxy_opts?.buffer_requests)
  form.proxyBufferResp = Boolean(route.proxy_opts?.buffer_responses)
  form.healthActivePath = route.health_active?.path || ''
  form.healthActiveInterval = route.health_active?.interval || ''
  form.healthActiveTimeout = route.health_active?.timeout || ''
  form.healthActiveHeaders = headerValuesToLines(route.health_active?.headers || {})
  form.healthPassiveStatuses = (route.health_passive?.unhealthy_statuses || []).join(',')
  form.healthPassiveMaxFails = route.health_passive?.max_fails ?? ''
  form.healthPassiveFailDuration = route.health_passive?.fail_duration || ''
  form.transportDial = route.transport?.dial_timeout || ''
  form.transportKeepalive = route.transport?.keepalive || ''
  form.transportReadBuffer = route.transport?.read_buffer ?? ''
  form.transportWriteBuffer = route.transport?.write_buffer ?? ''
  form.transportTlsInsecure = Boolean(route.transport?.tls_insecure)
  if (route.redirect) {
    form.mode = 'redirect'
    form.redirectLocation = route.redirect.location || ''
    form.redirectCode = route.redirect.code ?? '302'
  } else if (route.respond) {
    form.mode = 'respond'
    form.respondStatus = route.respond.status ?? '200'
    form.respondBody = route.respond.body || ''
    form.respondContentType = route.respond.content_type || ''
  } else {
    form.mode = 'proxy'
  }
  form.overrides = (route.path_routes || []).map((ov) => ({
    id: ov.id || '',
    path: ov.path || '',
    stripPrefix: Boolean(ov.strip_prefix),
    enabled: ov.enabled !== false,
    methods: (ov.methods || []).join(', '),
    matchHeaders: headerValuesToLines(ov.match_headers || ov.matchHeaders || {}),
    upstreams:
      (ov.upstreams || []).map((u) => ({
        scheme: u.scheme || 'http',
        host: u.host || '',
        port: u.port ?? '',
        weight: u.weight ?? 1,
      })) || [emptyUpstream()],
    mode: ov.redirect ? 'redirect' : ov.respond ? 'respond' : 'proxy',
    redirectLocation: ov.redirect?.location || '',
    redirectCode: ov.redirect?.code ?? '302',
    respondStatus: ov.respond?.status ?? '200',
    respondBody: ov.respond?.body || '',
    respondContentType: ov.respond?.content_type || '',
  }))
  if (!form.overrides.length) form.overrides = []
}

function cancel() {
  emit('cancel')
}

function buildUpstreams(list) {
  return (list || [])
    .filter((u) => u.host && u.port)
    .map((u) => ({
      scheme: u.scheme || 'http',
      host: u.host.trim(),
      port: u.port,
      weight: u.weight || 1,
    }))
}

function buildRoutePayload() {
  const domains = form.domains
    .split(',')
    .map((domain) => domain.trim())
    .filter(Boolean)
    .map((domain) => {
      if (form.wildcard && !domain.startsWith('*.') && !domain.includes('*')) {
        return `*.${domain}`
      }
      return domain
    })

  const upstreams = buildUpstreams(form.upstreams)

  const payload = {
    domains,
    enabled: form.enabled,
    methods: form.methods
      .split(',')
      .map((m) => m.trim().toUpperCase())
      .filter(Boolean),
    match_headers: parseHeaderValues(form.matchHeaders),
    upstreams,
    lb_policy: form.lbPolicy,
    request_body_max_mb: form.maxBody === '' ? null : form.maxBody,
    timeouts: {
      connect: form.timeoutConnect === '' ? null : form.timeoutConnect,
      read: form.timeoutRead === '' ? null : form.timeoutRead,
      write: form.timeoutWrite === '' ? null : form.timeoutWrite,
    },
    headers_up: parseHeaderLines(form.headersUp),
    response_headers: parseHeaderLines(form.headersDown),
    proxy_opts: {
      flush_interval: form.proxyFlush,
      buffer_requests: form.proxyBufferReq,
      buffer_responses: form.proxyBufferResp,
    },
    health_active: form.healthActivePath
      ? {
          path: form.healthActivePath,
          interval: form.healthActiveInterval,
          timeout: form.healthActiveTimeout,
          headers: parseHeaderValues(form.healthActiveHeaders),
        }
      : null,
    health_passive:
      form.healthPassiveStatuses || form.healthPassiveMaxFails || form.healthPassiveFailDuration
        ? {
            unhealthy_statuses: form.healthPassiveStatuses
              .split(/[,\\s]+/)
              .map((s) => s.trim())
              .filter(Boolean),
            max_fails: form.healthPassiveMaxFails === '' ? null : form.healthPassiveMaxFails,
            fail_duration: form.healthPassiveFailDuration,
          }
        : null,
    transport: {
      dial_timeout: form.transportDial,
      keepalive: form.transportKeepalive,
      read_buffer: form.transportReadBuffer,
      write_buffer: form.transportWriteBuffer,
      tls_insecure: form.transportTlsInsecure,
    },
    options_response: form.optionsEnabled
      ? { enabled: true, status: Number(form.optionsStatus) || 204 }
      : null,
    redirect:
      form.mode === 'redirect'
        ? { location: form.redirectLocation, code: Number(form.redirectCode) || 302 }
        : null,
    respond:
      form.mode === 'respond'
        ? {
            status: Number(form.respondStatus) || 200,
            body: form.respondBody,
            content_type: form.respondContentType,
          }
        : null,
    path_routes: form.overrides
      .filter((o) => o.path)
      .map((o) => ({
        id: o.id || undefined,
        path: o.path.trim(),
        strip_prefix: o.stripPrefix,
        enabled: o.enabled,
        methods: o.methods
          .split(',')
          .map((m) => m.trim().toUpperCase())
          .filter(Boolean),
        match_headers: parseHeaderValues(o.matchHeaders),
        upstreams: buildUpstreams(o.upstreams),
        redirect:
          o.mode === 'redirect'
            ? { location: o.redirectLocation, code: Number(o.redirectCode) || 302 }
            : null,
        respond:
          o.mode === 'respond'
            ? {
                status: Number(o.respondStatus) || 200,
                body: o.respondBody,
                content_type: o.respondContentType,
              }
            : null,
        timeouts: {
          connect: form.timeoutConnect === '' ? null : form.timeoutConnect,
          read: form.timeoutRead === '' ? null : form.timeoutRead,
          write: form.timeoutWrite === '' ? null : form.timeoutWrite,
        },
      })),
  }
  return payload
}

function submit() {
  localError.value = ''
  try {
    const payload = buildRoutePayload()
    if (!payload.domains.length) {
      localError.value = 'Укажите хотя бы один домен'
      return
    }
    if (!payload.upstreams.length && form.mode === 'proxy') {
      localError.value = 'Добавьте хотя бы один апстрим'
      return
    }
    emit('submit', payload, reset)
  } catch (error) {
    localError.value = error.message || 'Ошибка формы'
  }
}

defineExpose({ reset, prefill })
</script>

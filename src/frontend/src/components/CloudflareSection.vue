<template>
  <section class="cloudflare">
    <div class="section-header">
      <h2>Cloudflare Tunnel</h2>
      <div class="cf-actions">
        <span class="status-pill" :class="statusClass">{{ statusText }}</span>
        <button class="ghost" type="button" @click="$emit('refresh')">Обновить</button>
        <button class="ghost" type="button" @click="$emit('start-docker')">Запустить tunnel</button>
        <button class="ghost" type="button" @click="$emit('apply')">Применить</button>
        <button class="ghost" type="button" @click="showHelp = true">Помощь</button>
      </div>
    </div>
    <p class="cf-note">
      Все HTTP/HTTPS домены и поддомены направляются на Caddy через fallback:
      <strong>{{ model.fallback || model.defaultService }}</strong>. Hostname-правила нужны только для
      исключений (например SSH на git).
    </p>
    <div class="cloudflare-grid">
      <div v-if="loading" class="empty">Загружаем hostnames...</div>
      <div v-else-if="!model.hostnames.length" class="empty">Исключения не добавлены.</div>
      <div v-else class="routes-grid">
        <CloudflareCard
          v-for="entry in model.hostnames"
          :key="entry.hostname"
          :entry="entry"
          @toggle="$emit('toggle', $event)"
          @edit="handleEdit"
          @delete="$emit('delete', $event)"
        />
      </div>
      <div class="panel cf-panel">
        <h2>Публичный hostname</h2>
        <CloudflareForm
          ref="formRef"
          :default-service="model.defaultService"
          :error="error"
          @submit="handleSubmit"
        />
      </div>
    </div>
  </section>
  <div v-if="showHelp" class="modal-backdrop" @click.self="showHelp = false">
    <div class="modal">
      <h3>Как запустить Cloudflare Tunnel</h3>
      <p>Токен должен быть выпущен на аккаунт, не на зону. Минимальные права:</p>
      <ul>
        <li>Account · Cloudflare Tunnel: Edit</li>
        <li>Zone · DNS: Edit (для доменов, где создаём CNAME на туннель)</li>
        <li>Optional: Zone · Read (для автоподстановки зон)</li>
      </ul>
      <p>
        Выпустить токен: <a href="https://dash.cloudflare.com/profile/api-tokens" target="_blank" rel="noreferrer">Cloudflare API Tokens</a>.
      </p>
      <p>
        Проверить токен: <code>curl -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" https://api.cloudflare.com/client/v4/accounts/verify</code>
      </p>
      <p>После сохранения токена нажмите «Запустить tunnel». Контейнер <code>tunel-cloudflared</code> стартует в host сети и тянет конфиг из токена.</p>
      <div class="modal-actions">
        <button class="ghost" type="button" @click="showHelp = false">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import CloudflareCard from './CloudflareCard.vue'
import CloudflareForm from './CloudflareForm.vue'

const props = defineProps({
  model: {
    type: Object,
    required: true,
  },
  loading: {
    type: Boolean,
    required: true,
  },
  statusText: {
    type: String,
    required: true,
  },
  statusClass: {
    type: String,
    required: true,
  },
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['refresh', 'apply', 'toggle', 'delete', 'save', 'start-docker'])

const formRef = ref(null)
const showHelp = ref(false)

function handleSubmit(payload, reset) {
  emit('save', payload, reset)
}

function handleEdit(entry) {
  formRef.value?.prefill(entry)
}
</script>

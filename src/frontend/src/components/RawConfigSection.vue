<template>
  <section class="raw-config">
    <div class="section-header">
      <h2>Raw конфигурация</h2>
      <div class="cf-actions">
        <button class="ghost" type="button" @click="$emit('refresh')" :disabled="loading">
          Обновить
        </button>
        <button class="primary" type="button" @click="$emit('save')" :disabled="loading">
          Сохранить routes.json
        </button>
      </div>
    </div>
    <div v-if="loading" class="empty">Загружаем конфигурацию...</div>
    <div v-else class="raw-grid">
      <div class="panel">
        <h3>routes.json</h3>
        <textarea v-model="routesModel" rows="18" spellcheck="false"></textarea>
        <small>Изменения сразу пересоберут config.json5. Формат JSON.</small>
        <p class="error">{{ error }}</p>
      </div>
      <div class="panel">
        <h3>plugins.json</h3>
        <textarea :value="pluginsText" rows="18" readonly spellcheck="false"></textarea>
        <small>Глобальные настройки плагинов.</small>
      </div>
      <div class="panel">
        <h3>config.json5 (read-only)</h3>
        <textarea :value="configText" rows="18" readonly spellcheck="false"></textarea>
        <small>Генерируется автоматически из routes.json.</small>
      </div>
      <div v-if="showConverter" class="panel converter">
        <div class="converter-header">
          <h3>Caddyfile → JSON5</h3>
          <button class="ghost" type="button" @click="emitConvert" :disabled="converting">
            Конвертировать
          </button>
        </div>
        <textarea v-model="caddyModel" rows="8" spellcheck="false" placeholder="Вставьте Caddyfile"></textarea>
        <textarea :value="convertResult" rows="8" readonly spellcheck="false" placeholder="Результат JSON5"></textarea>
        <small>Использует встроенный caddy adapt (--adapter caddyfile).</small>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  routesText: {
    type: String,
    default: '',
  },
  configText: {
    type: String,
    default: '',
  },
  pluginsText: {
    type: String,
    default: '',
  },
  loading: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
  caddyInput: {
    type: String,
    default: '',
  },
  convertResult: {
    type: String,
    default: '',
  },
  converting: {
    type: Boolean,
    default: false,
  },
  showConverter: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['refresh', 'save', 'convert', 'update:routesText', 'update:caddyInput'])

const routesModel = computed({
  get: () => props.routesText,
  set: (value) => emit('update:routesText', value),
})

const caddyModel = computed({
  get: () => props.caddyInput,
  set: (value) => emit('update:caddyInput', value),
})

function emitConvert() {
  emit('convert')
}
</script>

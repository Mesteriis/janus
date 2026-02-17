<template>
  <div v-if="open" class="modal-backdrop" @click.self="$emit('close')">
    <div class="modal modal-large">
      <div class="section-header">
        <div>
          <h2>Raw конфигурация</h2>
          <p class="subtitle">Редактируйте только routes.json. config.json5 генерируется автоматически.</p>
        </div>
        <div class="cf-actions">
          <span v-if="validated" class="status-pill ok">Validated</span>
          <span v-else class="status-pill warn">Not validated</span>
          <button class="ghost" type="button" @click="$emit('validate')" :disabled="validating">Validate</button>
          <button class="primary" type="button" @click="$emit('apply')" :disabled="!canApply || applying">Apply</button>
        </div>
      </div>
      <div class="raw-grid">
        <div class="panel">
          <h3>routes.json (маршруты)</h3>
          <textarea v-model="routesModel" rows="18" spellcheck="false"></textarea>
          <small>Формат JSON. Только маршруты, без плагинов и L4. После изменения требуется validate.</small>
        </div>
        <div class="panel">
          <h3>config.json5 (read-only)</h3>
          <textarea :value="configText" rows="18" readonly spellcheck="false"></textarea>
          <small>Генерируется автоматически из routes.json.</small>
        </div>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="modal-actions">
        <button class="ghost" type="button" @click="$emit('close')">Закрыть</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  open: {
    type: Boolean,
    default: false,
  },
  routesText: {
    type: String,
    default: '',
  },
  configText: {
    type: String,
    default: '',
  },
  validated: {
    type: Boolean,
    default: false,
  },
  canApply: {
    type: Boolean,
    default: false,
  },
  validating: {
    type: Boolean,
    default: false,
  },
  applying: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['close', 'validate', 'apply', 'update:routesText'])

const routesModel = computed({
  get: () => props.routesText,
  set: (value) => emit('update:routesText', value),
})
</script>

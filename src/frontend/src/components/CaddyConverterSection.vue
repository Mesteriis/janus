<template>
  <section class="panel converter-panel">
    <div class="section-header">
      <div>
        <h2>Caddyfile → JSON5</h2>
        <p class="subtitle">Быстрый адаптер через встроенный caddy adapt.</p>
      </div>
      <div class="cf-actions">
        <button class="primary" type="button" @click="emitConvert" :disabled="converting">
          Конвертировать
        </button>
      </div>
    </div>
    <div class="converter-grid">
      <div class="panel">
        <h3>Вход (Caddyfile)</h3>
        <textarea v-model="caddyModel" rows="16" spellcheck="false" placeholder="Вставьте Caddyfile или используйте пример ниже."></textarea>
        <button class="ghost" type="button" @click="applyExample">Вставить пример</button>
      </div>
      <div class="panel">
        <h3>Выход (JSON5)</h3>
        <textarea :value="convertResult" rows="16" readonly spellcheck="false" placeholder="Результат JSON5"></textarea>
      </div>
    </div>
    <p v-if="error" class="error">{{ error }}</p>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
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
  error: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['convert', 'update:caddyInput'])

const caddyModel = computed({
  get: () => props.caddyInput,
  set: (value) => emit('update:caddyInput', value),
})

function emitConvert() {
  emit('convert')
}

function applyExample() {
  const sample = `example.com {\n  reverse_proxy http://127.0.0.1:8080\n}\n`
  emit('update:caddyInput', sample)
}
</script>

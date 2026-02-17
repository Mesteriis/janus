<template>
  <div class="kv-input">
    <div class="kv-row" v-for="(row, idx) in rows" :key="idx">
      <input
        v-model="row.key"
        type="text"
        :placeholder="keyPlaceholder"
      />
      <input
        v-model="row.value"
        type="text"
        :placeholder="valuePlaceholder"
      />
      <button class="ghost" type="button" @click="removeRow(idx)">Удалить</button>
    </div>
    <button class="ghost" type="button" @click="addRow">Добавить</button>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({}),
  },
  keyPlaceholder: {
    type: String,
    default: 'Ключ',
  },
  valuePlaceholder: {
    type: String,
    default: 'Значение',
  },
})

const emit = defineEmits(['update:modelValue'])

const rows = ref([])
let syncing = false

function buildRows(value) {
  return Object.entries(value || {}).map(([key, val]) => ({ key, value: String(val ?? '') }))
}

watch(
  () => props.modelValue,
  (value) => {
    syncing = true
    rows.value = buildRows(value)
    syncing = false
  },
  { immediate: true, deep: true }
)

watch(
  rows,
  (value) => {
    if (syncing) return
    const out = {}
    for (const row of value) {
      const key = (row.key || '').trim()
      if (!key) continue
      out[key] = row.value ?? ''
    }
    emit('update:modelValue', out)
  },
  { deep: true }
)

function addRow() {
  rows.value.push({ key: '', value: '' })
}

function removeRow(idx) {
  rows.value.splice(idx, 1)
}
</script>

<template>
  <div class="tag-input">
    <div class="tag-row">
      <input
        v-model="draft"
        type="text"
        :placeholder="placeholder"
        @keydown.enter.prevent="addTag"
      />
      <button class="ghost" type="button" @click="addTag">Добавить</button>
    </div>
    <div v-if="modelValue.length" class="tag-list">
      <span v-for="item in modelValue" :key="item" class="tag-pill">
        {{ item }}
        <button type="button" class="tag-remove" @click="removeTag(item)">×</button>
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [],
  },
  placeholder: {
    type: String,
    default: 'Введите значение',
  },
})

const emit = defineEmits(['update:modelValue'])

const draft = ref('')

function addTag() {
  const value = draft.value.trim()
  if (!value) return
  if (!props.modelValue.includes(value)) {
    emit('update:modelValue', [...props.modelValue, value])
  }
  draft.value = ''
}

function removeTag(value) {
  emit('update:modelValue', props.modelValue.filter((item) => item !== value))
}
</script>
